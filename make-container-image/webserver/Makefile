tag := $(shell date '+%Y-%m-%d-%H%M%S-webserver')
# FIXME: There are no secrets in this image so it doesn't need to be
# in the restricted section.
# This can be overriden on the command line.
webserver_image_name = docker-registry.discovery.wmnet/restricted/mediawiki-webserver

fqin := $(webserver_image_name):$(tag)

image:
	docker build \
		--pull \
		--build-arg "http_proxy=$(http_proxy)" \
		--build-arg "https_proxy=$(https_proxy)" \
		--build-arg "CACHEBUSTER=$(tag)" \
		--build-arg "MW_CONFIG_BRANCH=$(MW_CONFIG_BRANCH)" \
		--build-arg "GIT_BASE=$(GIT_BASE)" \
		-t $(fqin) \
		.
	echo $(fqin) > last-build.tmp
	mv last-build.tmp last-build

push:
	sudo /usr/local/bin/docker-pusher $(fqin)

build-and-push-image: image push

# Alternate building approach to be used by scap
new-build-and-push-image: new-webserver-image push

new-webserver-image: webserver-base-image
	./build-webserver-image $(fqin)
	echo $(fqin) > last-build.tmp
	mv last-build.tmp last-build

webserver-base-image:
	docker build --pull -f Dockerfile.webserver-base-image -t webserver-image-base .
