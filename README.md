# Simpleblog


```
$ pip install -r requirements.txt
```
```
$ manage.py deploy
```
```
$ manage.py runserver --host 0.0.0.0
```


### Heroku

2.
```
$ heroku login
Email: <youremail>
Password: <password>
```

3.
```
$ heroku create <your appname>
```

4.
```
$ heroku addons:add heroku-postgresql:hobby-dev
```

5.
```
$ heroku config:set ADMINEMAIL=<adminemail>
```

6.
```
$ git push heroku master
```

7.
```
$ heroku run python manage.py deploy
$ heroku restart
```
`http://<youapp>.herokuapp.com/`。

8.
```
$ heroku maintenance:on
$ git push heroku master
$ heroku run python manage.py deploy
$ heroku restart
$ heroku maintenance:off
```
