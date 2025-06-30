FROM python:3.9-alpine
COPY . /flask_server
WORKDIR /flask_server
RUN apk add --no-cache --virtual .build-deps gcc musl-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps
EXPOSE 9090
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:9090", "flask_server:app"]
