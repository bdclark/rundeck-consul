FROM python:2-alpine

# Add dumb-init for proper PID 1 management
ENV DUMB_INIT_VERSION 1.2.0
RUN set -ex \
  && apk add --no-cache --virtual .install-deps openssl \
  && wget "https://github.com/Yelp/dumb-init/releases/download/v${DUMB_INIT_VERSION}/dumb-init_${DUMB_INIT_VERSION}_amd64" \
  && wget "https://github.com/Yelp/dumb-init/releases/download/v${DUMB_INIT_VERSION}/sha256sums" \
  && grep "dumb-init_${DUMB_INIT_VERSION}_amd64$" sha256sums | sha256sum -c \
  && rm sha256sums \
  && mv dumb-init_${DUMB_INIT_VERSION}_amd64 /usr/bin/dumb-init \
  && chmod +x /usr/bin/dumb-init \
  && apk del .install-deps

RUN apk add --no-cache su-exec \
  && adduser -SH rundeck-consul \
  && pip install \
    bottle \
    python-consul

WORKDIR /app

COPY app.py config.json /app/

COPY start.sh /start.sh

EXPOSE 8080

CMD ["/start.sh"]
