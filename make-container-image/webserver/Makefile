# FIXME: Remove -test once Giuseppe signs off.
tag := $(shell date '+%Y-%m-%d-%H%M%S-webserver-test')
# FIXME: There are no secrets in this image so it doesn't need to be
# in the restricted section.
fqin := docker-registry.discovery.wmnet/restricted/mediawiki-webserver:$(tag)

image:
	docker build \
		--pull \
		--build-arg "http_proxy=$(http_proxy)" \
		--build-arg "https_proxy=$(https_proxy)" \
		--build-arg "CACHEBUSTER=$(tag)" \
		-t $(fqin) \
		.

push:
	sudo /usr/local/bin/docker-pusher $(fqin)

build-and-push-image: image push
