FROM docker-registry.wikimedia.org/php7.2-fpm
USER root
RUN apt-get update && apt-get install -y wmf-certificates php-luasandbox php-wikidiff2 rsync

RUN mkdir /srv/mediawiki && chown www-data: /srv/mediawiki
# Use a numeric id here instead www-data.  This is to satisfy Kubernetes policies used at WMF.
USER 33
