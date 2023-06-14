from datetime import datetime, timedelta
import logging
import os
from airflow import conf
from airflow import DAG
from airflow.models import Variable
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.postgres_operator import PostgresOperator
from airflow.operators.python_operator import PythonOperator
from airflow.operators import (StageToRedshiftOperator, LoadFactOperator,
                              LoadDimensionOperator, DataQualityOperator)
from airflow.hooks.S3_hook import S3Hook
from helpers import SqlQueries

#AWS_KEY = os.environ.get('AWS_KEY')
#AWS_SECRET = os.environ.get('AWS_SECRET')

default_args = {
    'owner': '',
    'depends_on_past': False,
    'start_date': datetime.now(),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'catchup': False,
}

dag = DAG('udac_example_dag',
          default_args=default_args,
          description='Load and transform data in Redshift with Airflow',
          schedule_interval='@hourly'
        )

start_operator = DummyOperator(
    task_id='Begin_execution',
    dag=dag
)

stage_events_to_redshift = StageToRedshiftOperator(
    task_id="stage_events",
    redshift_conn_id="redshift",
    aws_credentials_id="aws_credentials",
    table="staging_events",
    s3_bucket='udacity-dend',
    s3_key="log_data/",
    dag=dag
)

stage_songs_to_redshift = StageToRedshiftOperator(
    redshift_conn_id="redshift",
    aws_credentials_id="aws_credentials",
    table="staging_songs",
    s3_bucket='udacity-dend',
    s3_key="song_data",
    extra_params="json 'auto' compupdate off region 'us-west-2'",
    task_id='Stage_songs',
    dag=dag
)

load_songplays_table = LoadFactOperator(
    task_id='load_songplays_fact_table',
    redshift_conn_id="redshift",
    table="songplays",
    sql_source=SqlQueries.songplay_table_insert,
    dag=dag
)

load_user_dimension_table = LoadDimensionOperator(
    task_id='load_user_dim_table',
    redshift_conn_id="redshift",
    table="users",
    sql_source=SqlQueries.user_table_insert,
    dag=dag
)

load_song_dimension_table = LoadDimensionOperator(
    task_id='load_song_dim_table',
    redshift_conn_id="redshift",
    table="songs",
    sql_source=SqlQueries.song_table_insert,
    dag=dag
)

load_artist_dimension_table = LoadDimensionOperator(
    task_id='load_artist_dim_table',
    redshift_conn_id="redshift",
    table="artists",
    sql_source=SqlQueries.artist_table_insert,
    dag=dag
)

load_time_dimension_table = LoadDimensionOperator(
    task_id='load_time_dim_table',
    redshift_conn_id="redshift",
    table="time",
    sql_source=SqlQueries.time_table_insert,
    dag=dag
)

run_quality_checks = DataQualityOperator(
    task_id='run_data_quality_checks',
    redshift_conn_id="redshift",
    table="time",
    dq_checks=[
        {'check_sql': "SELECT COUNT(*) FROM users WHERE userid is null", 'expected_result': 0},
        {'check_sql': "SELECT COUNT(*) FROM songs WHERE songid is null", 'expected_result': 0},
        {'check_sql': "SELECT COUNT(*) FROM artists WHERE artistid is null", 'expected_result': 0},
        {'check_sql': "SELECT COUNT(*) FROM songsplays WHERE playid is null", 'expected_result': 0},
        {'check_sql': "SELECT COUNT(*) FROM time WHERE start_time is null", 'expected_result': 0}
    ],
    dag=dag
)

end_operator = DummyOperator(
    task_id='Stop_execution', 
    dag=dag
)

start_operator >> [stage_events_to_redshift, stage_songs_to_redshift]

[stage_events_to_redshift, stage_songs_to_redshift] >> load_songplays_table

load_songplays_table >> [load_user_dimension_table, load_song_dimension_table, load_artist_dimension_table, load_time_dimension_table]

[load_user_dimension_table, load_song_dimension_table, load_artist_dimension_table, load_time_dimension_table] >> run_quality_checks

run_quality_checks >> end_operator