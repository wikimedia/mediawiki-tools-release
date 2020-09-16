#-*-tab-width: 4; fill-column: 76; whitespace-line-column: 77 -*-
# vi:shiftwidth=4 tabstop=4 textwidth=76

FROM alpine:3.9
RUN apk add --no-cache	\
    git					\
    gnupg				\
    make				\
    python3				\
    util-linux			\
	wget
RUN pip3 install --upgrade pip git-archive-all requests
RUN ln -s /src/gitconfig /root/.gitconfig
COPY Makefile *.mk /
ENTRYPOINT ["make"]
