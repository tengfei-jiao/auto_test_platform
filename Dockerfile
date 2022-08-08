FROM python:3.8-buster
ENV PYTHONUNBUFFERED=1
ADD ./requirements.txt /app/requirements.txt

RUN sh -c "echo 'Asia/Shanghai' > /etc/timezone" \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && cd /app \
    && mkdir static \
    && pip install -r ./requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

#是否将源代码打包到镜像内？取决于什么因素？频繁的发版本就不要放里面了，只需要改下代码提价后，git自动拉取就好了
# ADD . /app

EXPOSE 8000
ENTRYPOINT cd /app; python manage.py collectstatic -c --no-input; gunicorn -b 0.0.0.0:8000 auto_test_platform.wsgi;
#是否加入python manage.py migrate？不管加不加，需要注意到对后续流程的影响