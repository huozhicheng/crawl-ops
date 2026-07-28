FROM python:3.10-slim

WORKDIR /app

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装编译依赖和时区数据
# 包含常用 Python 包所需的系统库：
# - libpq-dev: psycopg2 (PostgreSQL)
# - default-libmysqlclient-dev: mysqlclient (MySQL)
# - libxml2-dev, libxslt-dev: lxml
# - libjpeg-dev, zlib1g-dev, libpng-dev: Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    libffi-dev \
    python3-dev \
    tzdata \
    libpq-dev \
    default-libmysqlclient-dev \
    pkg-config \
    libxml2-dev \
    libxslt-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# 配置pip使用阿里云镜像
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com

# 升级pip并安装依赖
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 18081

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "18081"]
