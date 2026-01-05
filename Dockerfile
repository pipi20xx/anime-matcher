FROM python:3.11-slim

WORKDIR /app

# 先复制元数据和源码结构
COPY pyproject.toml README.md ./
COPY src/ ./src/

# 安装项目及其依赖
RUN pip install --no-cache-dir .

# 设置 PYTHONPATH 确保能找到包
ENV PYTHONPATH=/app/src

EXPOSE 8000

# 运行微服务
CMD ["python", "-m", "anime_matcher.main"]