from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, window
from pyspark.sql.types import StructType, IntegerType, StringType, TimestampType
import pyspark.sql.functions as funcs

"""
常量
"""
spark_master = "spark://spark-master:7077"
kafka_master = "kf1:9092,kf2:9092"
mnet_topic = "mnet"
mnet_agg_topic = "mnet_agg"
window_time = "30 seconds"

spark = SparkSession.builder.master(
    spark_master
).getOrCreate()

stream_data = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", kafka_master) \
    .option("subscribe", mnet_topic) \
    .load()
stream_data.printSchema()

# kafka json数据解析
data_schema = StructType().add(
    "host", StringType()
).add(
    "event_time", TimestampType()
).add(
    "netflow", StructType().add(
        "ipv4_src_addr", StringType()
    ).add(
        "ipv4_dst_addr", StringType()
    ).add(
        "in_bytes", IntegerType()
    ).add(
        "in_pkts", IntegerType()
    ).add(
        "protocol", IntegerType()
    )
)
new_stream_data = stream_data.select(
    stream_data.key.cast("string"),
    from_json(stream_data.value.cast("string"), data_schema).alias('json_data')
)
new_stream_data.printSchema()

new_df = new_stream_data.filter(
    (new_stream_data.json_data.netflow.protocol == 6) | (new_stream_data.json_data.netflow.protocol == 17)
).select(
    (new_stream_data.json_data.netflow.ipv4_src_addr).alias('src_ip'),
    (new_stream_data.json_data.netflow.ipv4_dst_addr).alias('dest_ip'),
    (new_stream_data.json_data.netflow.in_bytes).alias('in_bytes'),
    (new_stream_data.json_data.netflow.in_pkts).alias('in_pkts'),
    (new_stream_data.json_data.event_time).alias('event_time'),
)
new_df.printSchema()

# 聚合
res_df = new_df.withWatermark(
    'event_time', window_time
).groupBy(
    new_df.src_ip,
    new_df.dest_ip,
    window(new_df.event_time, window_time, window_time),
).agg(
    funcs.count("*").alias("flows"),
    funcs.sum("in_bytes").alias("bytes"),
    funcs.sum("in_pkts").alias("packets"),
)
res_df.printSchema()

# Start running the query that prints the running counts to the console
query = res_df \
    .selectExpr("CAST(window AS STRING) AS key", "to_json(struct(*)) AS value") \
    .writeStream \
    .trigger(processingTime=window_time) \
    .outputMode("update") \
    .format("kafka") \
    .option("kafka.bootstrap.servers", kafka_master) \
    .option("topic", mnet_agg_topic) \
    .option("checkpointLocation", "/tmp/{}".format(mnet_agg_topic)) \
    .start() \
    .awaitTermination()
