"""
Created by James

I'm still pretty new with python, but hopefully nothing is too broken.
This file will (hopefully) act as a conduit between the sql server, and the REST interface
"""
from __future__ import with_statement
import os, sys, mysql.connector, hashlib, time
from mysql.connector import errorcode
from flask import Flask, request, session, flash, g, redirect, Response, json, escape

application = Flask(__name__)
application.debug = True

# config information stored in separate file for security
application.config.from_pyfile('shyft_config.py')
application.secret_key = application.config['FLASK_SECRET_KEY']



def connect_to_db():
    try:
        cnx = mysql.connector.connect(user=application.config['MYSQL_USERNAME'],
                                      password=application.config['MYSQL_PASSWORD'],
                                      host='www.shyftwrk.com',
                                      port=4454)
    except mysql.connector.Error as err:
        print(err)
        sys.exit(1)
    return cnx


@application.before_request
def before_request():
    g.db = connect_to_db()
    return


@application.after_request
def after_request(response):
    g.db.close()
    return response


@application.route('/<group>/accounts/user=new', methods=['POST'])  # remove the get eventually
#manipulates the shyftwrk user accounts table
def create_user(group):
    jResponse = {}
    if not 'username '+group in session:
        jResponse["queryCode"] = "failed"
        jResponse["reason"] = "please login!"
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
    else:
        if not 'username' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'username field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if not 'password' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'password field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if not 'first name' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'first name field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if not 'last name' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'last name field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if not 'admin' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'admin field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        #declare local variables
        username = request.form['username'].encode('utf-8')
        password = request.form['password'].encode('utf-8')
        firstname = request.form['first name'].encode('utf-8')
        lastname = request.form['last name'].encode('utf-8')
        adminbool = request.form['admin'].encode('utf-8')
        salt = os.urandom(16).encode('hex')
        md5pass = hashlib.md5()
        md5pass.update(salt + password)

        query = 'select username, password from shyftwrk.userlist where username = %s and organisation = %s'
        cursor = g.db.cursor()
        try:
            cursor.execute(query, (username, group))
        except mysql.connector.Error as err:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = "the following query failed: data/insert_staff, error code is' + err.msg"
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        for row in cursor.fetchall():
            if username == row[0].decode('utf-8'):
                return "username is already in database, please choose another username or login!"
        query = 'insert into shyftwrk.userlist(username, password, salt, first_name, last_name, organisation db_admin_perm)' \
                                            ' values (%s, %s, %s, %s,%s, %s, %s)'

        try:
            cursor.execute(query, (username, md5pass.hexdigest(), salt, firstname, lastname, group, adminbool))
        except mysql.connector.Error as err:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = "the following query failed: data/insert_staff, error code is' + err.msg"
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        g.db.commit()

        jResponse["queryCode"] = "success"
        jResponse['username'] = username
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')



@application.route('/<group>/accounts/login', methods=['POST'])
##input: username, password - output: login cookie, admin cookie (if applicable)
def login_user(group):
    jResponse = {}
    ## check if all form fields contain data, for some reason flask has trouble with not saying what it needs
    if not 'username' in request.form:
        jResponse["queryCode"] = "failed"
        jResponse["reason"] = 'username field is required.'
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
    if not 'password' in request.form:
        jResponse["queryCode"] = "failed"
        jResponse["reason"] = 'password field is required.'
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

    #declare local variables
    username = request.form['username'].encode('utf-8')
    password = request.form['password'].encode('utf-8')
    cursor = g.db.cursor()
    query = 'select username, password, salt from shyftwrk.userlist  where username = %s and organisation = %s'

    try:
        cursor.execute(query, (username, group))
    except mysql.connector.Error as err:
        jResponse["queryCode"] = "failed"
        jResponse["reason"] = "the following query failed: accounts/login, error code is' + err.msg"
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

    for row in cursor.fetchall():
        md5pass = hashlib.md5()
        md5pass.update(row[2].decode('utf-8') + password)
        if username == row[0].decode('utf-8') and md5pass.hexdigest() == row[1].decode('utf-8'):
            session['username '+group] = username
            jResponse['queryCode'] = 'success'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
    jResponse["queryCode"] = "failed"
    jResponse["reason"] = 'invalid username/password.'
    return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')


@application.route('/<group>/data/pull', methods=['GET'])
def data_pull_request(group): # creates a json output containing all staff with corresponding shift data objects pulled from sql
    jResponse = {}
    if not 'username ' + group in session:
        jResponse["queryCode"] = "failed"
        jResponse["reason"] = "please login"
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
    else:
        grouppattern = '%' + group + '%'
        cursor = g.db.cursor()
        query = 'select name, positions, portrait, uid, organisations from shyftwrk.staffdata where organisations like %s'
        try:
            cursor.execute(query, (grouppattern,))  # select all employees from the employee_data table
        except mysql.connector.Error as err:
                jResponse["queryCode"] = "failed"
                jResponse["reason"] = 'the following query failed: data/pulljson, error code is' + err.msg
                return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        staffdata = cursor.fetchall()
        jResponse['staff'] = {}
        for row, x in zip(staffdata, range(0, cursor.rowcount)):

            jResponse['staff']['employee'+str(x)] = {
                'name' : row[0].decode('utf-8'),
                'uid' : row[3].decode('utf-8'),
                'positions' : row[1],
                'portrait' : row[2].decode('utf-8'),
                'organisations' : row[4].decode('utf-8'),
                'shift data' : {} # fill this dict with shift data
            }
            chartQuery = 'select DATE_FORMAT(date,\'%d-%m-%y\') as date, performance, shift_scheduled, ' \
                         'position_scheduled, shift_id from shyftwrk.shyftdata where staff_id = %s and organisation = %s'
            try:
                cursor.execute(chartQuery, (row[3], group))
            except mysql.connector.Error as err:
                    jResponse["queryCode"] = "failed"
                    jResponse["reason"] = 'the following query failed: data/pulljson, error code is' + err.msg
                    return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
            shyftdata = cursor.fetchall()
            for shift_row, j in zip(shyftdata, range(0, cursor.rowcount)): # create new dictionaries for each shift item
                jResponse['staff']['employee'+str(x)]['shift data']['shift'+str(j)] = {}
                jResponse['staff']['employee'+str(x)]['shift data']['shift'+str(j)] = {
                    'date' : shift_row[0].encode('utf-8'),
                    'performance' : shift_row[1],
                    'shift scheduled' : shift_row[2],
                    'position scheduled' : shift_row[3],
                    'shift id' : shift_row[4],
                    'synergy' : {} #fill this dict with synergy data
                }

                synColQuery = 'select column_name from information_schema.columns where ' \
                               'table_schema = \'shyftwrk\' and table_name = \'shyftdata\''
                try:
                    cursor.execute(synColQuery)
                except mysql.connector.Error as err:
                    jResponse["queryCode"] = "failed"
                    jResponse["reason"] = 'the following query failed: data/pulljson, error code is' + err.msg
                    return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
                # col_data = cursor.fetchall()
                col_data = []
                syn_col_string = ' '
                for col_select in cursor.fetchall():
                    if 'syn_' in col_select[0].encode('utf-8'): #for each column, if it starts with syn_, its a synergy query
                        syn_col_string +=col_select[0].encode('utf-8') + ','
                        col_data.append(col_select[0].encode('utf-8'))
                syn_col_string = syn_col_string[:-1] # remove the trailing coma from the string for the query to work
                synergyQuery = 'select ' + syn_col_string + ' from shyftwrk.shyftdata where shift_id = %s'
                try:
                    cursor.execute(synergyQuery, (shift_row[4],))
                except mysql.connector.Error as err:
                    jResponse["queryCode"] = "failed"
                    jResponse["reason"] = 'the following query failed: data/pulljson, error code is' + err.msg
                    return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

                synergy_data = map(list, cursor.fetchall()) #its easier to just create a list of this, since we don't need to match anything
                l = 0
                for k in  range(0, len(col_data)):
                    if not row[3] in col_data[k]: #strip the syn_ cols that are of the same type as the parent
                        jResponse['staff']['employee'+str(x)]['shift data']['shift'+str(j)]['synergy']['synergy'+str(l)] = {}
                        jResponse['staff']['employee'+str(x)]['shift data']['shift'+str(j)]['synergy']['synergy'+str(l)]['column']=col_data[k]
                        jResponse['staff']['employee'+str(x)]['shift data']['shift'+str(j)]['synergy']['synergy'+str(l)]['data'] = synergy_data[0][k]
                        l=l+1
        jResponse["queryCode"] = "success"
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

@application.route('/<group>/data/staff=new', methods=['POST'])
def new_staff(group): #if a person doesn't have a UID, make them one, otherwise triple check that this isn't going to
    #make a redundant member
    jResponse = {}
    if not 'username ' + group in session:
        jResponse["queryCode"] = "failed"
        jResponse['reason'] = "please login"
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
    else:
        cursor = g.db.cursor()
        if not 'name' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'name field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if not 'portrait' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'portrait field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        #declare local variables
        if not 'uid' in request.form:
            uid = None
        else:
            uid = request.form['uid'].encode('utf-8')
        name = request.form['name'].encode('utf-8').title()
        portrait = request.form['portrait'].encode('utf-8')
        last_edited_by = session['username '+ group].encode('utf-8')


        if(uid != None): #if uid isn't none, check the database for that uid
            query = 'select uid, name, organisations from shyftwrk.staffdata where uid = %s'
            try:cursor.execute(query, (uid,))
            except mysql.connector.Error as err:
                jResponse["queryCode"] = "failed"
                jResponse["reason"] = 'the following query failed: data/new_staff, error code is' + err.msg
                return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
            staffdata = cursor.fetchone()
            if(name != staffdata[1].decode('utf-8')):
                jResponse["queryCode"] = "failed"
                jResponse["reason"] = 'naming mismatch, contact admin for name changes.'
                return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
            organisations = staffdata[2] + ', ' + group
            query = 'update shyftwrk.staffdata set organisations = %s where uid = %s'
            try:cursor.execute(query, (organisations, uid))
            except mysql.connector.Error as err:
                jResponse["queryCode"] = "failed"
                jResponse["reason"] = 'the following query failed: data/new_staff, error code is' + err.msg
                return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

            g.db.commit()

            jResponse['queryCode'] = 'success'
            jResponse['uid'] = uid
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        else: #if this is a new member without a uid
            uid = hashlib.md5()
            uid.update(os.urandom(20))
            uid.update(str(time.clock())) #add the current time, this should ensure uniqueness
            uid = uid.hexdigest()

            #double check that a person with the exact same name, portrait and positions isn't already in the database
            query = 'select uid from shyftwrk.staffdata where name like %s and portrait like %s' #
            try:
                cursor.execute(query, (name, portrait))
            except mysql.connector.Error as err:
                jResponse["queryCode"] = "failed"
                jResponse["reason"] = 'the following query failed: data/new_staff, error code is' + err.msg
                return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
            uid_checker =[]
            for row in cursor.fetchall():
                uid_checker.append(row[0].decode('utf-8'))
            if len(uid_checker) >0: # if the cursor fetches any data at all, return
                jResponse["queryCode"] = "failed"
                jResponse["reason"] = 'new staff appears similar to existing members in database.'
                jResponse["similarStaff"] = {}
                jResponse["similarStaff"] = uid_checker
                return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json') #make this a warning, not an error
            query = 'insert into shyftwrk.staffdata(uid, name, portrait, organisations, last_edit_by) ' \
                    'values(%s, %s,  %s, %s, %s)'

            try:cursor.execute(query, (uid, name, portrait, group, last_edited_by))
            except mysql.connector.Error as err:
                jResponse["queryCode"] = "failed"
                jResponse["reason"] = 'the following query failed: data/new_staff, error code is' + err.msg
                return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

            query = 'alter table shyftwrk.shyftdata add column '+ uid + ' float'

            try:cursor.execute(query)
            except mysql.connector.Error as err:
                jResponse["queryCode"] = "failed"
                jResponse["reason"] = 'the following query failed: data/new_staff, error code is' + err.msg
                return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

            g.db.commit()

            jResponse["queryCode"] = "success"
            jResponse['uid'] = uid
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

@application.route('/<group>/data/staff=edit', methods=['POST'])
def edit_staff(group):
    #declare jResponse
    jResponse = {}
    if not 'username '+group in session:
        jResponse["queryCode"] = "failed"
        jResponse['reason'] = "please login"
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
    else:
        cursor = g.db.cursor()
        if not 'name' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'name field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if not 'portrait' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'portrait field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if not 'uid' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'uid field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        #declare local variables
        name = request.form['name'].encode('utf-8')
        portrait = request.form['portrait'].encode('utf-8')
        uid = request.form['uid'].encode('utf-8')
        last_edited_by = session['username '+ group].encode('utf-8')

        query = 'select organisations from shyftwrk.staffdata where uid like %s' # pull organisations data for append
        try:
            cursor.execute(query, (uid,))
        except mysql.connector.Error as err:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'the following query failed: data/edit_staff, error code is' + err.msg
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        organisations = cursor.fetchone()
        organisations = organisations[0].encode('utf-8')
        if not '^'+group in organisations: #add security feature here so admin can't add every person, requires consent
            organisations.join(', ' + group)
        query = 'update shyftwrk.staffdata set name = %s, portrait = %s, organisations = %s, last_edit_by = %s' \
                ' where uid like %s'
        try:
            cursor.execute(query, (name,portrait, organisations, last_edited_by, uid))
        except mysql.connector.Error as err:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'the following query failed: data/edit_staff, error code is' + err.msg
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        g.db.commit()

        jResponse["queryCode"] = "success"
        jResponse["uid"] = uid
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

@application.route('/<group>/data/staff=delete', methods=['POST'])
def del_staff(group): #we never actually delete someone from our database unless specifically requested by that person"
    jResponse = {}
    if not 'username '+group in session:
        jResponse["queryCode"] = "failed"
        jResponse['reason'] = "please login"
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
    else:
        cursor = g.db.cursor()
        if not 'uid' in request.form:
            Response["queryCode"] = "failed"
            jResponse["reason"] = 'uid field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        uid = request.form['uid'].encode('utf-8')
        last_edited_by = session['username '+group].encode('utf-8')
        #double check that this person exists presently
        query = 'select uid, organisations from shyftwrk.staffdata where uid = %s'

        try:
            cursor.execute(query, (uid,))
        except mysql.connector.Error as err:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'the following query failed: data/delete_staff, error code is' + err.msg
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        data = cursor.fetchall() # this should always be 1, always. Don't think its worth the cycles testing for duplicates
        detection = len(data)
        if detection <=0:
            jResponse['queryCode'] = 'failed'
            jResponse['reason']= 'uid is not found'
            return Response(json.dumps(jResponse, indent=4, separators=(',',':')), mimetype='application/json')
        for row in data:
            if group not in row[1].decode('utf-8'):
                jResponse['queryCode'] = 'failed'
                jResponse['reason']= 'staff has already been removed from this organisation'
                return Response(json.dumps(jResponse, indent=4, separators=(',',':')), mimetype='application/json')
            organisations = row[1].decode('utf-8')
            organisations = organisations.replace(group+', ', "") #check if theres a version with a comma
            organisations = organisations.replace(group, "") #if there isn't (IE its the first item), delete it anyways
        query = 'update shyftwrk.staffdata set organisations = %s where uid = %s'
        try:
            cursor.execute(query, (organisations, uid))
        except mysql.connector.Error as err:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'the following query failed: data/delete_staff, error code is' + err.msg
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        g.db.commit()

        jResponse['queryCode'] = 'success'
        jResponse['uid'] = uid
        return Response(json.dumps(jResponse, indent=4, separators=(',',':')), mimetype='application/json')


@application.route('/<group>/data/shift=new', methods=['POST'])
def new_shift(group):
    #declare jResponse
    jResponse = {}
    if not 'username '+group in session:
        jResponse["queryCode"] = "failed"
        jResponse["reason"] = 'please login.'
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
    else:
        cursor = g.db.cursor()

        if not 'date' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'date field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if not 'shift scheduled' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'shift scheduled field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if not 'position scheduled' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'position scheduled field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if not 'uid' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'uid field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        #declare local variables
        date = request.form['date'].encode('utf-8')
        shift_scheduled = request.form['shift scheduled']
        position_scheduled = request.form['position scheduled'].encode('utf-8')
        uid = request.form['uid'].encode('utf-8')
        organisation = group
        last_edit_by = session['username'].encode('utf-8')

        query = 'select * from shyftwrk.shyftdata where staff_id like %s and date like %s and shift_scheduled like %s ' \
                'and organisation like %s and position_scheduled like %s'
        try:
            cursor.execute(query, (uid, date, shift_scheduled, organisation, position_scheduled))
        except mysql.connector.Error as err:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'the following query failed: data/new_shift, error code is' + err.msg
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        detection  = len(cursor.fetchall())
        if detection > 0: # check for duplicate shift entries
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = "duplicate shift detection."
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        query = 'insert into shyftwrk.shyftdata(shift_id, staff_id, date, shift_scheduled, position_scheduled,' \
                ' organisation, last_edit_by) values(NULL, %s, %s, %s, %s, %s, %s)'

        try:
            cursor.execute(query, (uid, date, shift_scheduled, position_scheduled, organisation, last_edit_by))
        except mysql.connector.Error as err:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'the following query failed: data/new_shift, error code is' + err.msg
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        g.db.commit()
        query = 'select LAST_INSERT_ID()'

        try:
            cursor.execute(query)
        except mysql.connector.Error as err:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'the following query failed: data/new_shift, error code is' + err.msg
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        lastid = cursor.fetchall()
        lastid = lastid[0]
        jResponse["queryCode"] = "success"
        jResponse['shift id'] = lastid
        g.db.commit()
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

@application.route('/<group>/data/shift=edit', methods=['POST'])
def edit_shift(group):
    jResponse = {}
    if not 'username '+group in session:
        jResponse["queryCode"] = "failed"
        jResponse["reason"] = 'please login.'
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
    else:
        cursor = g.db.cursor()

        if not 'date' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'date field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if not 'shift scheduled' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'shift scheduled field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if not 'position scheduled' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'position scheduled field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if not 'uid' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'uid field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        if 'shift id' in request.form:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'uid field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        #declare local variables
        date = request.form['date'].encode('utf-8')
        shift_scheduled = request.form['shift scheduled']
        position_scheduled = request.form['position scheduled'].encode('utf-8')
        uid = request.form['uid'].encode('utf-8')
        shift_id = request.form['shift id']
        last_edit_by = session['username'].encode('utf-8')
        #we don't need to ever update organisation as it can be assumed there will be no transfer between organisations
        #for a shift

        query = 'update shyftwrk.shyftdata set date = %s, shift_scheduled = %s, position_scheduled = %s, staff_id = %s' \
                ', last_edit_by = %s where shift_id = %s'
        try:cursor.execute(query, (date, shift_scheduled, position_scheduled, uid, last_edit_by, shift_id))
        except mysql.connector.Error as err:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'the following query failed: data/edit_shift, error code is' + err.msg
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

        jResponse['queryCode'] = 'success'
        jResponse['shift id'] = shift_id
        g.db.commit()
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')


@application.route('/<group>/data/shift=delete', methods=['POST'])
def delete_shift(group):
    jResponse = {}
    if not 'username '+group in session:
        jResponse["queryCode"] = "failed"
        jResponse["reason"] = 'please login.'
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
    else:
        cursor = g.db.cursor()
        if not 'shift id' in request.form:
            Response["queryCode"] = "failed"
            jResponse["reason"] = 'shift id field is required.'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        shift_id = request.form['shift id']
        #check if shift exists before deleting"
        query = 'select shift_id, organisation from shyftwrk.shyftdata where shift_id = %s'
        try:cursor.execute(query, (shift_id,))
        except mysql.connector.Error as err:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'the following query failed: data/edit_shift, error code is' + err.msg
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        data = cursor.fetchall()
        if len(data) <=0:
            jResponse['queryCode'] = 'failed'
            jResponse['reason'] = 'the shift has already been deleted'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        #if it does exist, lets check to see if its owned by this organisation.
        if not group in data[1].decode('utf-8'):
            jResponse['queryCode'] = 'failed'
            jResponse['reason'] = 'your organisation does not own this shift'
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        query = 'delete from shyftwrk.shyftdata where shift_id = %s and organisation = %s'
        try:cursor.execute(query, (shift_id, group))
        except mysql.connector.Error as err:
            jResponse["queryCode"] = "failed"
            jResponse["reason"] = 'the following query failed: data/edit_shift, error code is' + err.msg
            return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')
        jResponse['queryCode'] = 'success'
        jResponse['shift id'] = shift_id
        g.db.commit()
        return Response(json.dumps(jResponse, indent=4, separators=(',', ':')), mimetype='application/json')

if __name__ == '__main__':
    application.run()
