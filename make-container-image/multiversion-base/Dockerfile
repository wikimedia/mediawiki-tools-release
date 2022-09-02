FROM docker-registry.wikimedia.org/php7.4-fpm-multiversion-base
USER root
ARG MV_BASE_PACKAGES
RUN apt-get update && apt-get install -y rsync $MV_BASE_PACKAGES

ARG MV_EXTRA_CA_CERT
RUN if [ "$MV_EXTRA_CA_CERT" ]; then echo "$MV_EXTRA_CA_CERT" | base64 -d > /usr/local/share/ca-certificates/multiversion-base-extra-ca.crt; /usr/sbin/update-ca-certificates; fi

RUN mkdir /srv/mediawiki && chown www-data: /srv/mediawiki
# Use a numeric id here instead www-data.  This is to satisfy Kubernetes policies used at WMF.
USER 33
