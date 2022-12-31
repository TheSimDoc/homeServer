import os
import logging
import re
import subprocess
import time

from influxdb_client import InfluxDBClient
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.rest import ApiException
#from influxdb import InfluxDBClient
#import influxdb_client


def db_exists():
    '''returns True if the database exists'''
    dbs = client.get_list_database()
    for db in dbs:
        if db['name'] == dbname:
            return True
    return False

def wait_for_server(host, port, nretries=5):
    '''wait for the server to come online for waiting_time, nretries times.'''
    url = 'http://{}:{}'.format(host, port)
    waiting_time = 1
    for i in range(nretries):
        try:
            requests.get(url)
            return 
        except requests.exceptions.ConnectionError:
            get_module_logger(__name__).info('waiting for', url)
            time.sleep(waiting_time)
            waiting_time *= 2
            pass
    get_module_logger(__name__).info('cannot connect to', url)
    sys.exit(1)

def connect_db(host, port, reset):
    '''connect to the database, and create it if it does not exist'''
    global client
    get_module_logger(__name__).info('connecting to database: {}:{}'.format(host,port))
    client = InfluxDBClient(host, port, retries=5, timeout=1)
    wait_for_server(host, port)
    create = False
    if not db_exists():
        create = True
        get_module_logger(__name__).info('creating database...')
        client.create_database(dbname)
    else:
        get_module_logger(__name__).info('database already exists')
    client.switch_database(dbname)
    if not create and reset:
        client.delete_series(measurement=measurement)
        
def measure(nmeas):
    '''insert dummy measurements to the db.
    nmeas = 0 means : insert measurements forever. 
    '''
    i = 0
    if nmeas==0:
        nmeas = sys.maxsize
    for i in range(nmeas):
        x = i/10.
        y = math.sin(x)
        data = [{
            'measurement':measurement,
            'time':datetime.datetime.now(),
            'tags': {
                'x' : x
                },
                'fields' : {
                    'y' : y
                    },
            }]
        client.write_points(data)
        pprint.pprint(data)
        time.sleep(1)
        
def get_module_logger(mod_name):
    """
    To use this, do logger = get_module_logger(__name__)
    """
    logger = logging.getLogger(mod_name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s [%(name)-12s] %(levelname)-8s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger

def str2bool(v):
    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def check_connection():
    """Check that the InfluxDB is running."""
    get_module_logger(__name__).info("> Checking connection ...")
    client.api_client.call_api('/ping', 'GET')
    get_module_logger(__name__).info("ok")


def check_query(bucket, org):
    """Check that the credentials has permission to query from the Bucket"""
    get_module_logger(__name__).info("> Checking credentials for query ...")
    try:
        client.query_api().query(f"from(bucket:\"{bucket}\") |> range(start: -1m) |> limit(n:1)", org)
    except ApiException as e:
        # missing credentials
        if e.status == 404:
            raise Exception(f"The specified token doesn't have sufficient credentials to read from '{bucket}' "
                            f"or specified bucket doesn't exists.") from e
        raise
    get_module_logger(__name__).info("ok")


def check_write(bucket, org):
    """Check that the credentials has permission to write into the Bucket"""
    get_module_logger(__name__).info("> Checking credentials for write ...")
    try:
        client.write_api(write_options=SYNCHRONOUS).write(bucket, org, b"")
    except ApiException as e:
        # bucket does not exist
        if e.status == 404:
            raise Exception(f"The specified bucket does not exist.") from e
        # insufficient permissions
        if e.status == 403:
            raise Exception(f"The specified token does not have sufficient credentials to write to '{bucket}'.") from e
        # 400 (BadRequest) caused by empty LineProtocol
        if e.status != 400:
            raise
    get_module_logger(__name__).info("ok")

class BatchingCallback(object):

    def success(self, conf: (str, str, str), data: str):
        """Successfully writen batch."""
        get_module_logger(__name__).info("Written batch: {conf}, data: {data}")

    def error(self, conf: (str, str, str), data: str, exception: InfluxDBError):
        """Unsuccessfully writen batch."""
        get_module_logger(__name__).info("Cannot write batch: {conf}, data: {data} due: {exception}")

    def retry(self, conf: (str, str, str), data: str, exception: InfluxDBError):
        """Retryable error."""
        get_module_logger(__name__).info("Retryable error occurs for batch: {conf}, data: {data} retry: {exception}")

callback = BatchingCallback()

__name__ = 'homeserver-speedtest-cli'

# Fetch environmental variables
testinterval = int(os.environ.get('TEST_INTERVAL',10))
writeCSV = str2bool(os.environ.get('WRITE_CSV',False))
writeInfluxDB = str2bool(os.environ.get('WRITE_INFLUXDB',True))
writeInfluxDB2 = str2bool(os.environ.get('WRITE_INFLUXDB2',True))
influxDBhost = os.environ.get('INFLUXDB_HOST','localhost')
influxDBorg = os.environ.get('INFLUXDB_ORG','mayr')
influxDBport = int(os.environ.get('INFLUXDB_PORT',8086))
influxDBdatabase = os.environ.get('INFLUXDB_DB','speedtest')
influxDBusername = os.environ.get('INFLUXDB_USER','influxdb')
influxDBpassword = os.environ.get('INFLUXDB_USER_PASSWORD','spdtstspdtstspdtst')
influxDBtoken = os.environ.get('INFLUXDB_INIT_ADMIN_TOKEN','spdtstabcdefghxyz')

get_module_logger(__name__).info("Set testinterval to %d seconds" % testinterval)
get_module_logger(__name__).info("Set writeCSV to %s" % writeCSV)
get_module_logger(__name__).info("Set writeInfluxDB to %s" % writeInfluxDB)
get_module_logger(__name__).info("Set writeInfluxDB2 to %s" % writeInfluxDB2)
get_module_logger(__name__).info("Set influxDB host to %s" % influxDBhost)
get_module_logger(__name__).info("Set influxDB port to %d" % influxDBport)
get_module_logger(__name__).info("Set influxDB database to %s" % influxDBdatabase)
get_module_logger(__name__).info("Set influxDB username host to %s" % influxDBusername)
get_module_logger(__name__).info("Set influxDB password port to %s" % influxDBpassword)
get_module_logger(__name__).info("Set influxDB token to %s" % influxDBtoken)

# conduct speedtest
get_module_logger(__name__).info("conduct speedtest")
response = subprocess.Popen('speedtest-cli --simple', shell=True, stdout=subprocess.PIPE).stdout.read().decode('utf-8')
ping = re.findall('Ping:\s(.*?)\s', response, re.MULTILINE)
download = re.findall('Download:\s(.*?)\s', response, re.MULTILINE)
upload = re.findall('Upload:\s(.*?)\s', response, re.MULTILINE)

ping = ping[0].replace(',', '.')
download = download[0].replace(',', '.')
upload = upload[0].replace(',', '.')

get_module_logger(__name__).info('Ping: ' + str(ping) + ' ms, Download: ' + str(download) + ' Mbit/s Upload: '+ str(upload) + ' Mbit/s')
get_module_logger(__name__).info('Waiting for ' + str(testinterval) + ' seconds')

if writeCSV==True:
    get_module_logger(__name__).info('Write data to csv File')
    try:
        f = open('./speedtest.csv', 'a+')
        if os.stat('./speedtest.csv').st_size == 0:
                f.write('Date,Time,Ping (ms),Download (Mbit/s),Upload (Mbit/s)\r\n')
    except:
        pass

    f.write('{},{},{},{},{}\r\n'.format(time.strftime('%m/%d/%y'), time.strftime('%H:%M'), ping, download, upload))

if writeInfluxDB==True:
    get_module_logger(__name__).info('create data for influxdb')
    speed_data = [
        {
            "measurement" : "internet_speed",
            "tags" : {
                "host": "speedtest"
            },
            "fields" : {
                "download": float(download),
                "upload": float(upload),
                "ping": float(ping)
            }
        }
    ]
    get_module_logger(__name__).info('connect to influxDB')
    client = InfluxDBClient(host=influxDBhost, port=influxDBport, database=influxDBdatabase, username=influxDBusername, password=influxDBpassword)
    get_module_logger(__name__).info('write data to influxDB')
    client.write_points(speed_data)

if writeInfluxDB2==True:
    get_module_logger(__name__).info('create data for influxdb2')
    speed_data = [
        {
            "measurement" : "internet_speed",
            "tags" : {
                "host": "speedtest"
            },
            "fields" : {
                "download": float(download),
                "upload": float(upload),
                "ping": float(ping)
            }
        }
    ]    
    get_module_logger(__name__).info('connecting to influxDB2')
    get_module_logger(__name__).info('URL: http://'+str(influxDBhost)+':'+str(influxDBport))
    with InfluxDBClient(url='http://'+str(influxDBhost)+':'+str(influxDBport), token=influxDBtoken, org=influxDBorg) as client:
        check_connection()
        #check_query(influxDBdatabase,influxDBorg)
        version = client.version()
        get_module_logger(__name__).info('InfluxDB: '+ str(version))
        check_write(influxDBdatabase,influxDBorg)
        get_module_logger(__name__).info('Writing data to influxDB2')
        with client.write_api(success_callback=callback.success,
                          error_callback=callback.error,
                          retry_callback=callback.retry) as write_api:
            write_api.write(bucket=influxDBdatabase, record=speed_data)
            get_module_logger(__name__).info('Writing data to influxDB2 finished')

time.sleep(testinterval)
