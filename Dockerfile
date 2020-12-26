FROM python:3

ADD report_generator.py /
ADD edgehostname.py /
ADD config_parser.py /
ADD basepageparse.py /

ADD requirements.txt /

RUN pip install -r requirements.txt
RUN pip install xlsxwriter
RUN apt-get update && apt-get install -yq dnsutils && apt-get clean && rm -rf /var/lib/apt/lists

ENTRYPOINT [ "python", "report_generator.py" ]
