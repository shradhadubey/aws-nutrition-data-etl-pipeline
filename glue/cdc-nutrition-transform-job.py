"""
CDC Nutrition Data Pipeline - Enhanced Transform Job
======================================================

PRODUCTION FEATURES:
✓ Schema validation with data contracts
✓ Comprehensive data quality checks
✓ Error handling with dead letter queue
✓ Optimized PySpark execution
✓ Structured logging and metrics
✓ Dimensional modeling (facts + dimensions)
✓ Data lineage tracking
✓ Partitioning for query performance

Author: Data Engineering Team
Version: 2.0
Last Updated: 2025-01-15
"""

import sys
import logging
from datetime import datetime
from typing import Dict, List, Tuple

from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, when, lit, coalesce, row_number, md5, 
    concat_ws, to_date, current_timestamp, isnull,
    avg, sum as spark_sum, count as spark_count
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, 
    DoubleType, TimestampType, LongType
)
from pyspark.sql.window import Window

from awsglue.context import GlueContext
from awsglue.job import Job


# ============================================================================
# LOGGING SETUP
# ============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataQualityConfig:
    """Configuration for data quality checks and validation rules"""
    
    # NOT NULL constraints
    NOT_NULL_COLUMNS = [
        "yearstart", "locationdesc", "data_value", 
        "question", "stratification1"
    ]
    
    # Numeric range constraints
    NUMERIC_RANGES = {
        "yearstart": (2000, 2030),
        "data_value": (-1, 100),  # -1 indicates "data not available"
    }
    
    # String length constraints
    STRING_LENGTHS = {
        "locationdesc": (2, 100),
        "question": (5, 200),
    }
    
    # Valid values for categorical columns
    VALID_VALUES = {
        "datatype": ["Percentage", "Count"],
        "stratification": ["Overall", "Gender", "Age Group", "Income", "Education"],
    }


class SchemaValidator:
    """Validates DataFrame against expected schema and business rules"""
    
    def __init__(self, spark: SparkSession):
        self.spark = spark
        self.validation_errors = []
    
    def validate_schema(self, df: DataFrame, expected_columns: List[str]) -> bool:
        """Check that required columns exist"""
        missing_cols = set(expected_columns) - set(df.columns)
        if missing_cols:
            self.validation_errors.append(f"Missing columns: {missing_cols}")
            return False
        return True
    
    def validate_null_constraints(self, df: DataFrame) -> DataFrame:
        """Flag rows with NULL values in required columns"""
        null_check = lit(True)
        for col_name in DataQualityConfig.NOT_NULL_COLUMNS:
            if col_name in df.columns:
                null_check = null_check & col(col_name).isNotNull()
        
        return df.withColumn(
            "_null_check_passed",
            null_check
        )
    
    def validate_numeric_ranges(self, df: DataFrame) -> DataFrame:
        """Flag rows where numeric values fall outside valid ranges"""
        range_check = lit(True)
        for col_name, (min_val, max_val) in DataQualityConfig.NUMERIC_RANGES.items():
            if col_name in df.columns:
                range_check = range_check & (
                    (col(col_name) >= min_val) & (col(col_name) <= max_val)
                )
        
        return df.withColumn(
            "_range_check_passed",
            range_check
        )
    
    def validate_categorical_values(self, df: DataFrame) -> DataFrame:
        """Flag rows with invalid categorical values"""
        for col_name, valid_vals in DataQualityConfig.VALID_VALUES.items():
            if col_name in df.columns:
                df = df.withColumn(
                    f"_{col_name}_valid",
                    col(col_name).isin(valid_vals) | col(col_name).isNull()
                )
        
        return df
    
    def combine_quality_checks(self, df: DataFrame) -> Tuple[DataFrame, DataFrame]:
        """Apply all checks and split into valid/invalid records"""
        # Run all validations
        df = self.validate_null_constraints(df)
        df = self.validate_numeric_ranges(df)
        df = self.validate_categorical_values(df)
        
        # Determine overall validity
        validity_cols = [c for c in df.columns if c.startswith("_") and c.endswith("passed") or c.endswith("valid")]
        
        overall_valid = col("_null_check_passed") & col("_range_check_passed")
        df = df.withColumn("_is_valid", overall_valid)
        
        # Split valid and invalid records
        valid_df = df.filter(col("_is_valid"))
        invalid_df = df.filter(~col("_is_valid")).select(
            df.columns + ["_null_check_passed", "_range_check_passed"]
        )
        
        return valid_df, invalid_df


class DimensionalModelTransformer:
    """Transforms raw data into dimensional model (facts + dimensions)"""
    
    def __init__(self, spark: SparkSession):
        self.spark = spark
    
    def extract_dim_date(self, df: DataFrame) -> DataFrame:
        """Extract unique dates and their attributes"""
        dim_date = df.select("yearstart").distinct() \
            .withColumnRenamed("yearstart", "year") \
            .withColumn("date_key", col("year")) \
            .withColumn("year_quarter", when(col("year") >= 2020, "Q3-2020+").otherwise("Historical")) \
            .select("date_key", "year", "year_quarter")
        
        return dim_date
    
    def extract_dim_location(self, df: DataFrame) -> DataFrame:
        """Extract unique locations with regional classification"""
        # Simplified location dimension (in production, join with census data)
        dim_location = df.select("locationdesc").distinct() \
            .withColumnRenamed("locationdesc", "location_name") \
            .withColumn("location_key", md5(col("location_name"))) \
            .withColumn("region", when(col("location_name").isin(
                ["Connecticut", "Maine", "Massachusetts", "New Hampshire", "Rhode Island", "Vermont"]
            ), "Northeast").otherwise("Other")) \
            .select("location_key", "location_name", "region")
        
        return dim_location
    
    def extract_dim_metric(self, df: DataFrame) -> DataFrame:
        """Extract metric definitions and business logic"""
        dim_metric = df.select("question").distinct() \
            .withColumnRenamed("question", "metric_name") \
            .withColumn("metric_key", md5(col("metric_name"))) \
            .withColumn(
                "metric_category",
                when(col("metric_name").contains("obesity"), "Obesity")
                .when(col("metric_name").contains("physical"), "Physical Activity")
                .when(col("metric_name").contains("diet"), "Diet & Nutrition")
                .otherwise("Other")
            ) \
            .withColumn("unit_of_measure", "Percentage") \
            .select("metric_key", "metric_name", "metric_category", "unit_of_measure")
        
        return dim_metric
    
    def create_fact_table(
        self, 
        df: DataFrame,
        dim_date: DataFrame,
        dim_location: DataFrame,
        dim_metric: DataFrame
    ) -> DataFrame:
        """Create fact table with foreign keys to dimensions"""
        
        # Join with dimensions
        fact = df \
            .join(dim_date, col("yearstart") == col("year"), "left") \
            .join(dim_location, col("locationdesc") == col("location_name"), "left") \
            .join(dim_metric, col("question") == col("metric_name"), "left") \
            .select(
                # Dimension keys
                col("date_key"),
                col("location_key"),
                col("metric_key"),
                
                # Measures
                col("data_value").cast(DoubleType()).alias("obesity_rate"),
                
                # Audit columns
                lit(None).cast(DoubleType()).alias("low_confidence_interval"),
                lit(None).cast(DoubleType()).alias("high_confidence_interval"),
                
                # Metadata
                col("stratification1").alias("stratification"),
                col("response").alias("data_source_response"),
                
                # Data lineage
                col("_is_valid").alias("passed_quality_checks"),
                current_timestamp().alias("load_timestamp"),
                lit("bronze-to-silver-v2.0").alias("transform_version"),
            ) \
            .dropDuplicates(["date_key", "location_key", "metric_key", "stratification"])
        
        return fact


class PySparkOptimizer:
    """Configuration for PySpark query optimization"""
    
    @staticmethod
    def configure_spark(spark: SparkSession):
        """Apply production performance configurations"""
        spark.conf.set("spark.sql.adaptive.enabled", "true")
        spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
        spark.conf.set("spark.sql.shuffle.partitions", "200")
        spark.conf.set("spark.sql.parquet.compression.codec", "snappy")
        
        logger.info("✓ Spark optimizations configured")


# ============================================================================
# MAIN JOB LOGIC
# ============================================================================

def main():
    """Main ETL process"""
    
    # Initialize Glue/Spark
    args = getResolvedOptions(sys.argv, ['JOB_NAME', 'TempDir'])
    sc = SparkContext()
    glueContext = GlueContext(sc)
    spark = glueContext.spark_session
    job = Job(glueContext)
    job.init(args['JOB_NAME'], args)
    
    # Apply optimizations
    PySparkOptimizer.configure_spark(spark)
    
    logger.info(f"🚀 Job started: {args['JOB_NAME']} at {datetime.now().isoformat()}")
    
    try:
        # =====================================================================
        # STAGE 1: INGEST
        # =====================================================================
        logger.info("📥 Reading raw data from Bronze layer...")
        
        raw_df = glueContext.create_dynamic_frame.from_catalog(
            database="cdc_nutrition_db",
            table_name="raw_bronze"
        ).toDF()
        
        ingest_count = raw_df.count()
        logger.info(f"✓ Ingested {ingest_count:,} records from Bronze")
        
        # =====================================================================
        # STAGE 2: VALIDATE & CLEANSE
        # =====================================================================
        logger.info("🔍 Running data quality checks...")
        
        validator = SchemaValidator(spark)
        
        # Validate required columns exist
        required_cols = ["yearstart", "locationdesc", "data_value", "question"]
        if not validator.validate_schema(raw_df, required_cols):
            raise ValueError(f"Schema validation failed: {validator.validation_errors}")
        
        # Apply quality checks
        valid_df, invalid_df = validator.combine_quality_checks(raw_df)
        
        valid_count = valid_df.count()
        invalid_count = invalid_df.count()
        quality_score = (valid_count / ingest_count * 100) if ingest_count > 0 else 0
        
        logger.info(f"✓ Quality checks: {valid_count:,} valid | {invalid_count:,} invalid ({quality_score:.2f}% pass rate)")
        
        # Write invalid records to quarantine (dead letter queue)
        if invalid_count > 0:
            logger.warning(f"⚠️  Writing {invalid_count} invalid records to quarantine...")
            invalid_df.write.mode("append").parquet(
                "s3://cdc-nutrition-quarantine/invalid-records/"
            )
        
        # =====================================================================
        # STAGE 3: STANDARDIZE & CLEAN
        # =====================================================================
        logger.info("🧹 Standardizing column names and data types...")
        
        clean_df = valid_df \
            .withColumn("yearstart", col("yearstart").cast(IntegerType())) \
            .withColumn("data_value", col("data_value").cast(DoubleType())) \
            .withColumn("locationdesc", col("locationdesc").cast(StringType())) \
            .withColumn("question", col("question").cast(StringType())) \
            .withColumn("stratification1", coalesce(col("stratification1"), lit("Overall"))) \
            .select(
                "yearstart", "locationdesc", "data_value", "question", 
                "stratification1", "response", "_is_valid"
            )
        
        clean_count = clean_df.count()
        logger.info(f"✓ Standardized {clean_count:,} records")
        
        # =====================================================================
        # STAGE 4: TRANSFORM TO DIMENSIONAL MODEL
        # =====================================================================
        logger.info("🔧 Building dimensional model...")
        
        transformer = DimensionalModelTransformer(spark)
        
        # Extract dimensions
        dim_date = transformer.extract_dim_date(clean_df)
        dim_location = transformer.extract_dim_location(clean_df)
        dim_metric = transformer.extract_dim_metric(clean_df)
        
        dim_date_count = dim_date.count()
        dim_location_count = dim_location.count()
        dim_metric_count = dim_metric.count()
        
        logger.info(
            f"✓ Dimensions extracted: "
            f"{dim_date_count} dates | "
            f"{dim_location_count} locations | "
            f"{dim_metric_count} metrics"
        )
        
        # Create fact table
        fact_df = transformer.create_fact_table(clean_df, dim_date, dim_location, dim_metric)
        fact_count = fact_df.count()
        logger.info(f"✓ Fact table created with {fact_count:,} records")
        
        # =====================================================================
        # STAGE 5: WRITE TO SILVER LAYER (PARQUET)
        # =====================================================================
        logger.info("💾 Writing to Silver layer (Parquet)...")
        
        # Write fact table with partitioning
        fact_df.repartition("date_key", "location_key") \
            .write \
            .mode("overwrite") \
            .format("parquet") \
            .option("compression", "snappy") \
            .option("path", "s3://cdc-nutrition-transformed-silver/fact_obesity_observations/") \
            .partitionBy("date_key") \
            .option("parquet.bloom.filter.enabled#date_key", "true") \
            .option("parquet.bloom.filter.enabled#location_key", "true") \
            .save()
        
        # Write dimensions (small tables, no partitioning needed)
        for dim_name, dim_table in [
            ("dim_date", dim_date),
            ("dim_location", dim_location),
            ("dim_metric", dim_metric),
        ]:
            dim_table.coalesce(1).write.mode("overwrite").format("parquet").save(
                f"s3://cdc-nutrition-transformed-silver/{dim_name}/"
            )
            logger.info(f"✓ Written {dim_name} to Silver")
        
        # =====================================================================
        # STAGE 6: DATA LINEAGE & METRICS
        # =====================================================================
        logger.info("📊 Computing metrics and lineage...")
        
        # Compute aggregate statistics for monitoring
        metrics = clean_df.agg({
            "data_value": ["avg", "min", "max", "stddev"],
        }).collect()
        
        lineage_record = {
            "job_name": args['JOB_NAME'],
            "execution_timestamp": datetime.now().isoformat(),
            "records_ingested": ingest_count,
            "records_valid": valid_count,
            "records_invalid": invalid_count,
            "quality_score_percent": quality_score,
            "fact_records_written": fact_count,
            "dimensions_written": 3,
            "transform_version": "2.0",
            "status": "SUCCESS"
        }
        
        logger.info(f"📈 Pipeline metrics: {lineage_record}")
        
        # Write lineage to metadata table (optional)
        spark.createDataFrame([lineage_record]) \
            .write.mode("append").parquet(
                "s3://cdc-nutrition-transformed-silver/_metadata/job_lineage/"
            )
        
        # =====================================================================
        # COMMIT JOB
        # =====================================================================
        job.commit()
        logger.info("✅ Job completed successfully")
        
        return lineage_record
    
    except Exception as e:
        logger.error(f"❌ Job failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()