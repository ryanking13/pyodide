FROM node:20.11-bookworm-slim AS node-image
FROM python:3.13.2-slim-bookworm

# Requirements for building packages
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
        bzip2 ccache f2c g++ gfortran git make \
        patch pkg-config swig unzip wget xz-utils \
        autoconf autotools-dev automake texinfo dejagnu \
        build-essential libtool libltdl-dev \
        gnupg2 libdbus-glib-1-2 sudo sqlite3 \
        ninja-build jq \
  && rm -rf /var/lib/apt/lists/*

# install autoconf 2.71, required by upstream libffi
RUN wget https://mirrors.ocf.berkeley.edu/gnu/autoconf/autoconf-2.71.tar.xz \
    && tar -xf autoconf-2.71.tar.xz \
    && cd autoconf-2.71 \
    && ./configure \
    && make install \
    && cp /usr/local/bin/autoconf /usr/bin/autoconf \
    && rm -rf autoconf-2.71

ADD requirements.txt /

WORKDIR /
RUN pip3 --no-cache-dir install -r requirements.txt \
    && rm requirements.txt

RUN cd / \
    && git clone --recursive https://github.com/WebAssembly/wabt \
    && cd wabt \
    && git submodule update --init \
    && make install-gcc-release-no-tests \
    && cd ~  \
    && rm -rf /wabt

COPY --from=node-image /usr/local/bin/node /usr/local/bin/
COPY --from=node-image /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN npm install -g \
  jsdoc \
  prettier \
  rollup \
  rollup-plugin-terser

# Normally, it is a bad idea to install rustup and cargo in
# system directories (it should not be shared between users),
# but this docker image is only for building packages, so I hope it is ok.
# Setting RUSTUP_UPDATE_ROOT gives us a beta rustup.
# TODO: Remove when Rustup 1.28.0 is released.
RUN wget -q -O  -  https://sh.rustup.rs | \
  RUSTUP_UPDATE_ROOT=https://dev-static.rust-lang.org/rustup \
  RUSTUP_HOME=/usr CARGO_HOME=/usr \
  sh -s -- -y --profile minimal --no-modify-path

ARG CHROME_VERSION="latest"
ARG FIREFOX_VERSION="latest"

# Download selenium manager binary to download and cache browsers and web drivers
RUN wget -q https://github.com/SeleniumHQ/selenium_manager_artifacts/releases/download/selenium-manager-c28783f/selenium-manager-linux -O /usr/local/bin/selenium-manager \
  && chmod +x /usr/local/bin/selenium-manager \
  && /usr/local/bin/selenium-manager --force-browser-download --browser chrome --browser-version $CHROME_VERSION \
  && /usr/local/bin/selenium-manager --force-browser-download --browser firefox --browser-version $FIREFOX_VERSION

CMD ["/bin/sh"]
WORKDIR /src
