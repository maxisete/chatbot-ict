FROM python:3.11-slim

RUN useradd -m -u 1000 user
WORKDIR /app

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN chown -R user /app
USER user

EXPOSE 7860

CMD ["bash", "start.sh"]
