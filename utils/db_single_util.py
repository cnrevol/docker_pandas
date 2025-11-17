import psycopg2
import pandas as pd
from pathlib import Path
import yaml
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
import traceback
import sys
import math
import re,os

pattern = re.compile(r"\$\{([^}^{]+)\}")  # 匹配 ${VAR_NAME}

def env_constructor(loader, node):
    value = loader.construct_scalar(node)
    matches = pattern.findall(value)
    for match in matches:
        env_value = os.getenv(match, "")
        value = value.replace(f"${{{match}}}", env_value)
    return value

# 注册自定义 tag
yaml.SafeLoader.add_constructor("tag:yaml.org,2002:str", env_constructor)

def load_db_params_from_yaml(config_path="database_config.yml"):
    config_file_path = Path(__file__).resolve().parent.parent / "config" / config_path
    with open(config_file_path, "r") as config_file:
        config_data = yaml.safe_load(config_file)
    return config_data["db_params"]  # Assuming "db_params" is the key in your YAML

    

class Database:
    def __init__(self, db_params=None,logger =None):
        self.logger = logger

        if db_params is None:
            db_params = load_db_params_from_yaml()
        self.db_params = db_params
        self.engine = create_engine(self.init_engine_constr())

    def init_engine_constr(self):
        self.logger.info('Init connection_string.')
        connection_string = (
            f"postgresql://{self.db_params['username']}:{self.db_params['password']}@{self.db_params['host']}:{self.db_params['port']}/{self.db_params['database']}?options=-c search_path={self.db_params['schema']} "
        )
        # self.logger.info(f'connection_string is {connection_string}')
        return connection_string
    
    def execute_query_col_name(self, query, params=None):
        # Create an SQLAlchemy engine
        # engine = create_engine(self.init_engine_constr())

        # Use the engine with pd.read_sql_query
        result = pd.read_sql_query(query, self.engine, params=params)
        return result
    
    def execute_insert_query(self, query, params=None):
        try:
            # 获取数据库连接
            with self.engine.connect() as connection:
                # 执行插入操作
                result = connection.execute(query, params)
                self.logger.info("Insert successful.")
                
                # 如果需要获取插入的自增主键，可以通过 result.lastrowid 获取
                # last_inserted_id = result.lastrowid
                # print("Last Inserted ID:", last_inserted_id)

        except Exception as e:
            self.logger.error(f"Error executing insert query: {e}")

    def execute_update_query(self, query, params=None):
        try:
            # 获取数据库连接
            with self.engine.connect() as connection:
                # 执行更新操作
                result = connection.execute(query, params)
                self.logger.info("Update successful.")
                
        except Exception as e:
            self.logger.error(f"Error executing update query: {e}")



    def execute_query_to_pandas(self, query, params=None):
        # Use the engine with pd.read_sql_query
        result = pd.read_sql_query(query, self.engine, params=params)
        return result
    
    def update_table(self,df,tablename):
        df.to_sql(tablename, self.engine, if_exists="append", index=False)

    def upsert_table(self, df, tablename):
        self.logger.info(f'Update DB Table :{tablename}.')
        ret = False

        metadata = MetaData()
        table = Table(tablename, metadata, autoload_with=self.engine)
        primary_key_columns = table.primary_key.columns.keys()
        conn = self.engine.connect()

        # 检查 DataFrame 的列是否存在于表中
        valid_columns = [col for col in df.columns if col in table.columns]
        # 仅选择 DataFrame 中存在于表中的列
        df = df[valid_columns]

        # 去掉主键重复值
        unique_df = df.drop_duplicates(subset=primary_key_columns)

        # Split the DataFrame into chunks of 1000 records
        chunk_size = 1000
        num_chunks = math.ceil(len(unique_df) / chunk_size)
        chunks = [unique_df[i * chunk_size:(i + 1) * chunk_size] for i in range(num_chunks)]

        for chunk in chunks:
            stmt = insert(table).values(chunk.to_dict(orient='records'))
            set_dict = {col.name: stmt.excluded[col.name] for col in table.columns}
            for key in primary_key_columns:
                del set_dict[key]

            stmt = stmt.on_conflict_do_update(index_elements=primary_key_columns, set_=set_dict)
            ret = True
            
            try:
                conn.execute(stmt)
            except IntegrityError as e1:
                self.logger.error(f"Exception Message: {e1.orig}")
                # self.logger.error(f"Exception: {e1}")
                self.logger.error(traceback.format_exc())
                line_number = traceback.extract_tb(sys.exc_info()[2])[-1][1]
                self.logger.error(f"Failed Records number:{line_number}")
            except Exception as e2:
                self.logger.error(f"Exception: {e2}")
            
        conn.close()
        return ret
    

