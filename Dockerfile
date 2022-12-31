FROM python:3

# Add the python script
ADD homeserver-speedtest-cli.py /

# Install required Python packages
RUN pip install speedtest-cli
#RUN pip install influxdb
RUN pip install influxdb_client

#ARG tst_int=60
#ARG wrt_csv=False
#ARG wrt_iflxDB=True

#ENV TEST_INTERVAL=$tst_int
#ENV WRITE_CSV=$wrt_csv
#ENV WRITE_INFLUXDB=$wrt_iflxDB

RUN env
# Set the working directory to /app
# in the container
#WORKDIR /app
#CMD [ "python", "./rpi-speedtest-cli.py" ]
CMD ["python", "-u", "./homeserver-speedtest-cli.py"]#, "-t ", $TEST_INTERVAL, "-c ", $WRITE_CSV, " -i ", $WRITE_INFLUXDB]
