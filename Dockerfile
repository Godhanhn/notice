FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，使得 Python 输出不被缓冲，这样可以在容器日志中实时看到输出
ENV PYTHONUNBUFFERED=1

# 将 requirements.txt 拷贝到工作目录
COPY requirements.txt .

# 安装依赖，使用 --no-cache-dir 减小镜像体积
RUN pip install --no-cache-dir -r requirements.txt

# 将代码拷贝到工作目录
COPY main.py .

# 创建持久化数据的目录
RUN mkdir -p data

# 运行主程序
CMD ["python", "main.py"]
