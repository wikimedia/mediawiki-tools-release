tag := $(shell date '+%Y-%m-%d-%H%M%S-webserver')
# FIXME: There are no secrets in this image so it doesn't need to be
# in the restricted section.
fqin := docker-registry.discovery.wmnet/restricted/mediawiki-webserver:$(tag)

image:
	docker build \
		--pull \
		--build-arg "http_proxy=$(http_proxy)" \
		--build-arg "https_proxy=$(https_proxy)" \
		--build-arg "CACHEBUSTER=$(tag)" \
		--build-arg "BRANCH=$(BRANCH)" \
		--build-arg "GIT_BASE=$(GIT_BASE)" \
		-t $(fqin) \
		.
	echo $(fqin) > last-build.tmp
	mv last-build.tmp last-build

push:
	sudo /usr/local/bin/docker-pusher $(fqin)

build-and-push-image: image push
