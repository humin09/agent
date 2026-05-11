FROM image.ac.com:5000/k8s/ske-model-tool:v1

# 安装必要的 Python 依赖
RUN pip install --no-cache-dir aiohttp requests

# 复制 maas-test.py
COPY maas-test.py /usr/local/bin/maas-test.py
RUN chmod +x /usr/local/bin/maas-test.py

# 设置工作目录和入口点
WORKDIR /tmp
CMD ["python", "/usr/local/bin/maas-test.py", "--help"]
