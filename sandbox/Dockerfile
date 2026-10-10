FROM docker.io/library/gcc:14.2.0-bookworm@sha256:82549aa8f90ada3236a8be70c74543132a76662ef33f0c3271ed802b81584a82

COPY container_runner.cpp /tmp/container_runner.cpp
RUN g++ -std=c++20 -O2 -pipe -fno-diagnostics-color \
    /tmp/container_runner.cpp -o /usr/local/bin/firsterchuv-container-runner \
    && rm -f /tmp/container_runner.cpp \
    && chmod 0555 /usr/local/bin/firsterchuv-container-runner

USER 65534:65534
ENTRYPOINT ["/usr/local/bin/firsterchuv-container-runner"]
