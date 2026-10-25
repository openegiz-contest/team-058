FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir paho-mqtt==2.1.0
COPY engine.py continuous.py server.py setup_twins.py OPENMINES_LICENSE ./
COPY data/ ./data/
COPY static/ ./static/
ENV PYTHONUNBUFFERED=1 OREFLOW_PORT=8099
EXPOSE 8099
CMD ["python", "server.py"]
