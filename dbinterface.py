"""
Created by James

I'm still pretty new with python, but hopefully nothing is too broken.
This file will (hopefully) act as a conduit between the sql server, and the REST interface
"""
from __future__ import with_statement
import os, sys, mysql.connector, hashlib
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
    if not 'username '+group in session:
        return json.jsonify({'error' :'please login!'})
    # create local user variables
    else:

        if not 'username' in request.form:
            return json.jsonify({'error': 'username field is required.'})
        if not 'password' in request.form:
            return json.jsonify({'error' : 'password field is required.'})
        if not 'first name' in request.form:
            return json.jsonify({'error': 'first name field is required'})
        if not 'last name' in request.form:
            return json.jsonify({'error' : 'last name field is required'})
        if not 'admin' in request.form:
            return json.jsonify({'error' : 'admin field is required'})


        username = request.form['username'].encode('utf-8')
        password = request.form['password'].encode('utf-8')
        firstname = request.form['first name'].encode('utf-8')
        lastname = request.form['last name'].encode('utf-8')
        adminbool = request.form['admin'].encode('utf-8')
        salt = os.urandom(16).encode('hex')
        md5pass = hashlib.md5()
        md5pass.update(salt + password)
        query = 'select username, password from shyftwrk.userlist where username = %s and organization = %s'
        cursor = g.db.cursor()
        try:
            cursor.execute(query, (username, group))
        except mysql.connector.Error as err:
            return json.jsonify({'error' : 'the following query failed: data/insert_staff, error code is' + err.msg})

        for row in cursor.fetchall():
            if username == row[0].decode('utf-8'):
                return "username is already in database, please choose another username or login!"
        query = 'insert into shyftwrk.userlist(username, password, salt, first_name, last_name, organization db_admin_perm)' \
                                            ' values (%s, %s, %s, %s,%s, %s, %s)'

        try:
            cursor.execute(query, (username, md5pass.hexdigest(), salt, firstname, lastname, group, adminbool))
        except mysql.connector.Error as err:
            return json.jsonify({'error' : 'the following query failed: data/insert_staff, error code is' + err.msg})
        g.db.commit()
        print cursor.statement
        return json.jsonify({'success' : "user %s was successfully inserted into database" % username})


@application.route('/<group>/accounts/login', methods=['POST'])
##input: username, password - output: login cookie, admin cookie (if applicable)
def login_user(group):
    ## check if all form fields contain data, for some reason flask has trouble with not saying what it needs
    if not 'username' in request.form:
        return json.jsonify({'error': 'username field is required.'})
    if not 'password' in request.form:
        return json.jsonify({'error' : 'password field is required.'})

    username = request.form['username'].encode('utf-8')
    password = request.form['password'].encode('utf-8')

    if 'username '+group in session and session['username '+group] == request.form['username']:
        return json.jsonify({'warning' :'you are already logged in as %s' % escape(username)})

    # create local user variables
    cursor = g.db.cursor()
    query = 'select username, password, salt from shyftwrk.userlist  where username = %s and organization = %s'

    try:
        cursor.execute(query, (username, group))
    except mysql.connector.Error as err:
        return json.jsonify({'error' : 'the following query failed: data/insert_staff, error code is' + err.msg})

    for row in cursor.fetchall():
        md5pass = hashlib.md5()
        md5pass.update(row[2].decode('utf-8') + password)
        if username == row[0].decode('utf-8') and md5pass.hexdigest() == row[1].decode('utf-8'):
            successResponse = Response(json.dumps({'success': 'you have successfully logged in'}, indent=4), mimetype='application/json')
            session['username '+group] = username
            return successResponse
    return Response(json.dumps({'error': 'username/password are invalid'}, indent=4), mimetype='application/json')


@application.route('/<group>/accounts/logoff')
def logout(group):
    if 'username '+group in session :
        session.pop()
        return "logged off"
    else:
        return "you are already logged out!"


@application.route('/<group>/data/pull', methods=['GET'])
def data_pull_request(group): # creates a json output containing all staff with corresponding shift data objects pulled from sql
    if not 'username ' + group in session:
        return 'please login!'
    else:
        grouppattern = '%' + group + '%'
        cursor = g.db.cursor()
        query = 'select name, positions, portrait, uid, organizations from shyftwrk.staffdata where organizations like %s'
        try:
            cursor.execute(query, (grouppattern,))  # select all employees from the employee_data table
        except mysql.connector.Error as err:
            return json.jsonify({'error' : 'the following query failed: data/pulljson, error code is' + err.msg})
        jsonstring = {}
        staffdata = cursor.fetchall()
        for row in staffdata:

            jsonstring[row[3]] = {
                'name' : row[0].decode('utf-8'),
                'positions' : row[1].decode('utf-8'),
                'portrait' : row[2].decode('utf-8'),
                'organizations' : row[4].decode('utf-8'),
                'shift data' : {} # fill this dict with shift data
            }
            chartQuery = 'select DATE_FORMAT(date,\'%d-%m-%y\') as date, performance, shift_scheduled, ' \
                         'position_scheduled, shift_id from shyftwrk.shyftdata where staff_id = %s and organization = %s'
            try:
                cursor.execute(chartQuery, (row[3], group))
            except mysql.connector.Error as err:
                return json.jsonify({'error' : 'the following query failed: data/pulljson, error code is' + err.msg})
            shyftdata = cursor.fetchall()
            for shift_row, j in zip(shyftdata, range(0, cursor.rowcount)): # create new dictionaries for each shift item
                jsonstring[row[3]]['shift data'][j] = {}
                jsonstring[row[3]]['shift data'][j] = {
                    'date' : shift_row[0].encode('utf-8'),
                    'performance' : shift_row[1],
                    'shift scheduled' : shift_row[2],
                    'position scheduled' : shift_row[3],
                    'shift_id' : shift_row[4],
                    'synergy' : {} #fill this dict with synergy data
                }

                synColQuery = 'select column_name from information_schema.columns where ' \
                               'table_schema = \'shyftwrk\' and table_name = \'shyftdata\''
                try:
                    cursor.execute(synColQuery)
                except mysql.connector.Error as err:
                    return json.jsonify({'error' : 'the following query failed: data/pulljson, error code is' + err.msg})
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
                    return json.jsonify({'error' : 'the following query failed: data/pulljson, error code is' + err.msg})

                synergy_data = map(list, cursor.fetchall()) #its easier to just create a list of this, since we don't need to match anything
                for k in  range(0, len(col_data)):
                    if not row[3] in col_data[k]: #strip the syn_ cols that are of the same type as the parent
                        jsonstring[row[3]]['shift data'][j]['synergy'][col_data[k]] = synergy_data[0][k]

        return Response(json.dumps(jsonstring, indent=4, separators=(',', ':')), mimetype='application/json')

@application.route('/<group>/data/staff=new', methods=['POST'])
def insert_staff(group):
    if not 'username '+group in session:
        return 'please login!'
    else:
        cursor = g.db.cursor()
        if 'name' in request.form:
            name = request.form['name'].encode('utf-8')
        else:
            return json.jsonify({'error': 'name field is required.'})
        if 'positions' in request.form:
            positions = request.form['positions'].encode('utf-8')
        else:
            return json.jsonify({'error' : 'position field is required'})
        if 'portrait' in request.form:
            portrait = request.form['portrait'].encode('utf-8')
        else:
            return json.jsonify({'error' : 'portrait field is required'})
        last_edited_by = session['username'].encode('utf-8')
        if 'has UID' in request.args:
            # UID = request.form['UID'].encode('utf-8') this is how it should be done, but for testing I will use args
            UID = request.args['UID'].encode('utf-8')
            query = 'select uid, name, positions, portrait, organizations from shyftwrk.staffdata where uid = %s'
            try:
                cursor.execute(query, (UID,))
            except mysql.connector.Error as err:
                return json.jsonify({'error' : 'the following query failed: data/insert_staff, error code is' + err.msg})
            staffdata = cursor.fetchone()
            if(name != staffdata[1].decode('utf-8')):
                flash("name is different, double check credentials")
                return "niggers"
        else: #double check that a person with the exact same name, portrait and positions isn't already in the database
            uid = hashlib.md5()
            uid.update(os.urandom(20))
            uid = uid.hexdigest()
            query = 'select uid from shyftwrk.staffdata where name like %s and positions like %s and portrait like %s'
            try:
                cursor.execute(query, (name, positions, portrait))
            except mysql.connector.Error as err:
                return json.jsonify({'error' : 'the following query failed: data/check_staff, error code is' + err.msg})

            uid_checker =[]
            for row in cursor.fetchall():
                uid_checker.append(row[0].decode('utf-8'))
            if len(uid_checker) >0: # if the cursor fetches any data at all, return
                return json.jsonify({'error' : 'new staff appears similar to existing members in database',
                                     'similar staff' : uid_checker})

            query = 'insert into shyftwrk.staffdata(uid, name, positions, portrait, organizations) ' \
                    'values(%s, %s, %s, %s, %s)'

            try:
                cursor.execute(query, (uid, name, positions, portrait, group))
            except mysql.connector.Error as err:
                return json.jsonify({'error' : 'the following query failed: data/insert_staff, error code is' + err.msg})
            synergyname = 'syn_' + uid

            query = 'alter table shyftwrk.shyftdata add column '+ synergyname + ' float';

            try:
                cursor.execute(query)
            except mysql.connector.Error as err:
                return json.jsonify({'error' : 'the following query failed: data/insert_staff, error code is' + err.msg})
            g.db.commit()
            return json.jsonify({'success':'person added', 'uid' : uid})

@application.route('/<group>/data/staff=edit', methods=['POST'])
def edit_staff(group):
    if not 'username '+group in session:
        return 'please login!'
    else:
        cursor = g.db.cursor()
        if 'uid' in request.form:
            uid = request.form['uid'].encode('utf-8')
        else:
            return json.jsonify({'error' : 'uid is required'})
        if 'name' in request.form:
            name = request.form['name'].encode('utf-8')
        else:
            return json.jsonify({'error': 'name field is required.'})
        if 'positions' in request.form:
            positions = request.form['positions'].encode('utf-8')
        else:
            return json.jsonify({'error' : 'position field is required'})
        if 'portrait' in request.form:
            portrait = request.form['portrait'].encode('utf-8')
        else:
            return json.jsonify({'error' : 'portrait field is required'})
        last_edited_by = session['username'].encode('utf-8')

        query = 'select organizations from shyftwrk.staffdata where uid like %s' # pull organizations data for append
        try:
            cursor.execute(query, (uid,))
        except mysql.connector.Error as err:
            return json.jsonify({'error' : 'the following query failed: data/edit_staff, error code is' + err.msg})
        organizations = cursor.fetchone()
        organizations = organizations[0].encode('utf-8')
        if not '^'+group in organizations: #add security feature here so admin can't add every person, requires consent
            organizations.join(', ' + group)
        query = 'update shyftwrk.staffdata set name = %s, positions = %s, portrait = %s, organizations = %s, last_edit_by = %s' \
                ' where uid like %s'
        try:
            cursor.execute(query, (name, positions, portrait, organizations, last_edited_by, uid))
        except mysql.connector.Error as err:
            return json.jsonify({'error' : 'the following query failed: data/edit_staff, error code is' + err.msg})

        g.db.commit()

        return json.jsonify({'success':'table has been updated', 'uid' : uid})

@application.route('/<group>/data/shift=new', methods=['POST'])
def new_shyft(group):
    if not 'username '+group in session:
        return json.jsonify({'error': 'please login!'})
    else:
        cursor = g.db.cursor()

        if 'date' in request.form:
            date = request.form['date'].encode('utf-8')
        else:
            return json.jsonify({'error' : 'date field is required'})

        if 'shift scheduled' in request.form:
            shift_scheduled = request.form['shift scheduled']
        else:
            return json.jsonify({'error' : 'shift scheduled field required'})

        if 'position scheduled' in request.form:
            position_scheduled = request.form['position scheduled'].encode('utf-8')
        else:
            return json.jsonify({'error' : 'position scheduled field required'})

        if 'uid' in request.form:
            uid = request.form['uid'].encode('utf-8')
        else:
            return json.jsonify({'error' : 'uid field is required'})

        organization = group
        last_edit_by = session['username'].encode('utf-8')

        query = 'select * from shyftwrk.shyftdata where staff_id like %s and date like %s and shift_scheduled like %s ' \
                'and organization like %s and position_scheduled like %s'
        try:
            cursor.execute(query, (uid, date, shift_scheduled, organization, position_scheduled))
        except mysql.connector.Error as err:
            return json.jsonify({'error' : 'the following query failed: data/new_shift, error code is' + err.msg})

        mysqldetection  = len(cursor.fetchall())
        if mysqldetection > 0: # check for duplicate shift entries
            return json.jsonify({'error' : 'duplicate shift detection!'})

        query = 'insert into shyftwrk.shyftdata(shift_id, staff_id, date, shift_scheduled, position_scheduled,' \
                ' organization, last_edit_by) values(NULL, %s, %s, %s, %s, %s, %s)'

        try:
            cursor.execute(query, (uid, date, shift_scheduled, position_scheduled, organization, last_edit_by))
        except mysql.connector.Error as err:
            return json.jsonify({'error' : 'the following query failed: data/new_shift, error code is' + err.msg})

        g.db.commit()
        query = 'select LAST_INSERT_ID()'

        try:
            cursor.execute(query)
        except mysql.connector.Error as err:
            return json.jsonify({'error' : 'the following query failed: data/new_shift, error code is' + err.msg})
        lastid = cursor.fetchall()
        lastid = lastid[0]
        return json.jsonify({'success' : 'shift successfully added', 'shift id' : lastid})

@application.route('/<group>/data/shift=edit', methods=['POST'])
def edit_shift(group):
    if not 'username '+group in session:
        return json.jsonify({'error': 'please login!'})
    else:
        cursor = g.db.cursor()

        if 'date' in request.form:
            date = request.form['date'].encode('utf-8')
        else:
            return json.jsonify({'error' : 'date field is required'})

        if 'shift scheduled' in request.form:
            shift_scheduled = request.form['shift scheduled']
        else:
            return json.jsonify({'error' : 'shift scheduled field required'})

        if 'position scheduled' in request.form:
            position_scheduled = request.form['position scheduled'].encode('utf-8')
        else:
            return json.jsonify({'error' : 'position scheduled field required'})

        if 'uid' in request.form:
            uid = request.form['uid'].encode('utf-8')
        else:
            return json.jsonify({'error' : 'uid field is required'})
        if 'shift id' in request.form:
            shift_id = request.form['shift id']
        else:
            return json.jsonify({'error' : 'shift id field is required'})

        last_edit_by = session['username'].encode('utf-8')

        query = 'update shyftwrk.shyftdata set date = %s, shift_scheduled = %s, position_scheduled = %s, staff_id = %s' \
                ', last_edit_by = %s where shift_id = %s'
        try:
            cursor.execute(query, (date, shift_scheduled, position_scheduled, uid, last_edit_by, shift_id))
        except mysql.connector.Error as err:
            return json.jsonify({'error' : 'the following query failed: data/edit_shift, error code is' + err.msg})

        return json.jsonify({'success' : 'successfully edited shift', 'shift id' : shift_id})
if __name__ == '__main__':
    application.run()
