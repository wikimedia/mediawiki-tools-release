# This file is roughly equivalent to https://gerrit.wikimedia.org/r/c/operations/mediawiki-config/+/708036/1/.pipeline/config.yaml

########
########
########

FROM docker-registry.wikimedia.org/buster as build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y git wmf-certificates

RUN mkdir /srv/mediawiki && chown www-data: /srv/mediawiki
# So the stager can run git config --global ...
RUN mkdir /var/www && chown www-data: /var/www

USER www-data

# CACHEBUSTER arg because we want git clone to run for every build
ARG CACHEBUSTER
ARG GIT_BASE
ARG BRANCH

COPY stage-srv-mediawiki /
RUN bash /stage-srv-mediawiki

########
########
########

FROM docker-registry.wikimedia.org/mediawiki-httpd
ARG CACHEBUSTER
RUN echo CACHEBUSTER value is $CACHEBUSTER
COPY --from=build /srv/mediawiki/ /srv/mediawiki/
