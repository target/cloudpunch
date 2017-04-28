import json

from flask import Flask

app = Flask(__name__)


@app.route('/api/system/health', methods=['GET'])
def get_syshealth():
    # Used to test if the API is up
    return json.dumps({'status': 'OK'}), 200, {'Content-Type': 'text/json; charset=utf-8'}


if __name__ == '__main__':
    app.run(host='127.0.0.1', threaded=True)
