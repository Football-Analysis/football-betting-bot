FROM python:3.13-slim

WORKDIR /betting-bot

COPY . /betting-bot

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-u", "main.py"]