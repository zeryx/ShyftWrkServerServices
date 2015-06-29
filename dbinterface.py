"""
Created by James

I'm still pretty new with python, but hopefully nothing is too broken.
This file will (hopefully) act as a conduit between the sql server, and the REST interface
"""
from __future__ import with_statement
import os
import mysql.connector
import hashlib
from flask import Flask, request, session, flash, g, redirect, url_for, abort, render_template, jsonify


application = Flask(__name__)
application.debug = True

def check_user():
    cursor = g.db.cursor()
    if not session.get('logged_in'):
        abort(401)
    return

def connect_to_db():
    cnx = mysql.connector.connect(user ='RESTful',
                              password ='ShyftWrk',
                              host = 'www.shyftwrk.com',
                              port= 4454)
    return cnx

@application.before_request
def before_request():
    g.db = connect_to_db()
    return

@application.route('/', methods=['GET'])
def show_names():
    cursor = g.db.cursor()
    query = 'select id, Name, Position from ShyftWrk.Employees'
    cursor.execute(query)
    for row in cursor.fetchall():
        jsonlist = jsonify(id=row[0],name=row[1], position=row[2])
    cursor.close()
    jsonstr = "json List"
    return jsonlist

@application.route('/account/newuser', methods=['POST'])
def create_user():
    cursor = g.db.cursor()
    username = [request.args['username'].encode('utf-8')]
    query = 'select User, Host from mysql.user where User like %s'
    cursor.execute(query, username)
    for row in cursor.fetchall():
        if username == row[0].decode('utf-8'):
            return "username is already in database, please choose another username or login!"

@application.route('/account/login', methods=['GET'])
def login_user():
    cursor = g.db.cursor()
    if request.method == 'GET':
        username = [request.args['username'].encode('utf-8')]
        password = [request.args['password'].encode('utf-8')]
        query = 'select username, password from shyftwrk_example.userlist where user like %s'
        cursor.execute(query, username)
        for row in cursor.fetchall():
            if username == row[0].decode('utf-8') and password == row[1].decode('utf-8'):
                session.set('logged_in')
                return "successfully logged in"
        return "username and/or password incorrect"
    return "incorrect http method"
@application.after_request
def after_request(response):
    g.db.close()
    return response



if __name__ == '__main__':
    application.run()