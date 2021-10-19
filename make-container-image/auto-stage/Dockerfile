FROM docker-registry.wikimedia.org/php7.2-cli

USER root

RUN apt-get update
RUN apt-get install -y jq git patch ca-certificates rsync

RUN mkdir -p /srv/mediawiki && chown www-data: /srv/mediawiki

RUN mkdir -p /var/www && chown www-data: /var/www

USER www-data

COPY /auto-stage /
COPY /PrivateSettings-train-dev.php /

ENTRYPOINT ["/auto-stage"]
