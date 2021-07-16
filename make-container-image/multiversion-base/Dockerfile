FROM docker-registry.wikimedia.org/php7.2-fpm
USER root
RUN apt-get update && apt-get install -y wmf-certificates php-luasandbox php-wikidiff2 rsync

RUN mkdir /srv/mediawiki && chown www-data: /srv/mediawiki
USER www-data
