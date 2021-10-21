# This file is roughly equivalent to https://gerrit.wikimedia.org/r/c/operations/mediawiki-config/+/708036/1/.pipeline/config.yaml

########
########
########

FROM docker-registry.wikimedia.org/buster as build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y git wmf-certificates

RUN mkdir /srv/mediawiki && chown www-data: /srv/mediawiki

USER www-data

# CACHEBUSTER arg because we want git clone to run for every build
ARG CACHEBUSTER
RUN echo CACHEBUSTER value is $CACHEBUSTER
RUN git clone --depth=1 https://gerrit.wikimedia.org/r/operations/mediawiki-config /srv/mediawiki
RUN git -C /srv/mediawiki submodule update --init --recursive
RUN cd /srv/mediawiki && rm -fr .git wmf-config tests php src multiversion

########
########
########

FROM docker-registry.wikimedia.org/mediawiki-httpd
ARG CACHEBUSTER
RUN echo CACHEBUSTER value is $CACHEBUSTER
COPY --from=build /srv/mediawiki/ /srv/mediawiki/
