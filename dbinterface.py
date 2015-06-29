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
    cnx = mysql.connector.connect(user ='testuser',
                              password ='test',
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

@application.route('/newAccount', methods=['GET', 'POST'])
def createUser():
    cursor = g.db.cursor()
    if request.method == 'POST':
        query = 'select User, Host from mysql.user where User like '.join(request.form['username'])
        if not cursor.execute(query):
            error = "username doesn't exist"
        else:
            return "you did it!" + request.form['username'] + "exists!"
    return "you fucked up"

@application.after_request
def after_request(response):
    g.db.close()
    return response



if __name__ == '__main__':
    application.run()