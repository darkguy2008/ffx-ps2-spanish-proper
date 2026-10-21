FROM maven:3-eclipse-temurin-25 AS parser
COPY vendor/FFXDataParser /FFXDataParser
RUN mvn -B -q -f /FFXDataParser/pom.xml package

FROM python:3.15-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends mono-devel mono-xbuild openjdk-25-jdk-headless \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PATH=/venv/bin:$PATH
COPY requirements.txt .
RUN python -m venv /venv && pip install --no-cache-dir -r requirements.txt
COPY vendor/vbfextract vendor/vbfextract
RUN xbuild /nologo /verbosity:quiet /p:Configuration=Release vendor/vbfextract/VBFTool.csproj
COPY --from=parser /FFXDataParser/target vendor/FFXDataParser/target
COPY patcher patcher
RUN mkdir build && mcs -nologo -warnaserror+ -out:build/extract_vbf.exe patcher/extract_vbf.cs
ENTRYPOINT ["python", "-u", "patcher/patch.py"]
