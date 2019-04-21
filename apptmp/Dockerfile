FROM alpine:3.7
RUN apk add python3 bash postgresql-dev build-base python3-dev
RUN pip3 install --upgrade pip
RUN pip3 install tornado psycopg2-binary asyncio aiopg
# RUN pip3 install psycopg2

WORKDIR /home/tornado
COPY . /home/tornado

EXPOSE 8888

# CMD ["python3", "/home/tornado/chat/chatdemo.py"]
CMD ["python3", "/home/tornado/chatdemo.py"]

# ENTRYPOINT ['./bin/bash']
