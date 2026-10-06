# LM Studio headless (llmster) serving an OpenAI-compatible API on :1234.
# Run ./fetch-llmster.sh first: it downloads the pinned bundle next to this file.
# The model weights are not baked in: mount them at /home/lms/.lmstudio/models.
FROM ubuntu:24.04
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl libatomic1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10002 lms
USER lms
WORKDIR /home/lms
COPY --chown=lms llmster.tar.gz /tmp/llmster.tar.gz
RUN mkdir /tmp/llmster && tar xf /tmp/llmster.tar.gz -C /tmp/llmster \
    && LMS_BOOTSTRAP_INSTALL_SH=1 /tmp/llmster/llmster bootstrap \
    && /home/lms/.lmstudio/bin/lms bootstrap -y \
    && rm -rf /tmp/llmster /tmp/llmster.tar.gz
ENV PATH=/home/lms/.lmstudio/bin:$PATH LLM_MODEL=qwen2.5-coder-1.5b-instruct
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
EXPOSE 1234
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=12 \
    CMD curl -fsS http://localhost:1234/v1/models | grep -q "$LLM_MODEL"
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
