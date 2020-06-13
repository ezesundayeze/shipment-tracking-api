from flask import Flask, jsonify, request
from flask_restful import Resource, Api, reqparse
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_cors import CORS
import jwt
import stream
import os
from dotenv import load_dotenv

# configuration
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

load_dotenv()
STREAM_SECRET_KEY = os.getenv("STREAM_SECRET_KEY")
STREAM_API_KEY = os.getenv("STREAM_API_KEY")


client = stream.connect(STREAM_API_KEY, STREAM_SECRET_KEY, location='us-east')

CORS(app, origins="*", allow_headers=[
    "Content-Type", "Authorization", "Access-Control-Allow-Credentials"],
    supports_credentials=True)

api = Api(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////' + os.path.join(basedir, 'db.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATION'] = False

db = SQLAlchemy(app)
ma = Marshmallow(app)


class Shipment(db.Model):
    """
    Shipment Model
    """
    id = db.Column(db.Integer, primary_key=True)
    destination = db.Column(db.String(80))
    source = db.Column(db.String(120))
    current_location = db.Column(db.String(120))
    status = db.Column(db.String(120))
    item = db.Column(db.String(120))
    description = db.Column(db.String(120))
    tracking_number = db.Column(db.String(120), nullable=True)
    arrival = db.Column(db.String(120))

    def __repr__(self):
        return '<Shipment %r>' % self.item

    def __init__(self, description, source, current_location, status, item, tracking_number, arrival, destination):
        
        self.description =  description
        self.destination =  destination
        self.source = source
        self.current_location = current_location
        self.status = status
        self.item = item
        self.tracking_number = tracking_number
        self.arrival = arrival

class ShipmentSchema(ma.Schema):
    """
    Schema
    """
    class Meta:
        fields = (
        'id', 
        'item', 
        'description', 
        'status', 
        'tracking_number',
        'current_location',
        'source',
        'destination',
        'description',
        'arrival'
        )

shipment_schema = ShipmentSchema()
shipments_schema = ShipmentSchema(many=True)

class GenerateToken(Resource):
    """
    API to generate token to authenticate users
    """
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("user_id", type=str)
        parser.add_argument('Authorization', location='headers')
        data =  parser.parse_args()
        user_id =data.get("user_id")
        
        user_token = client.create_user_token(user_id)
        return ({'token': user_token})


class ShipmentView(Resource):
    """
    Shipment management API
    """

    def get(self, id=None):
        """
        get Shipment
        """
        try:
            if id is None:
                shipment = Shipment.query.filter().all()
                shipment_schema =  ShipmentSchema(many=True)
                return shipment_schema.dump(shipment)
            else:
                shipment = Shipment.query.filter_by(id=id).first()
                shipment_schema = ShipmentSchema()
                return shipment_schema.dump(shipment)

        except Exception as e:
            print(e)

    def post(self):
    
        """
        Add shipment
        """
        data = request.get_json()

        token = data['headers']['Authorization']   

        # decode token
        user = jwt.decode(token[7:], STREAM_SECRET_KEY)

        # Instantiate a feed object
        user_feed = client.feed('user', user['user_id'])

        try:
            del data['headers']
            new_shipment = Shipment(**data)
            db.session.add(new_shipment)
            db.session.commit()

            """ 
            Add an activity to the feed, where actor, 
            object and target are references to objects (`Eric`, `Hawaii`, `Places to Visit`)
            """
            activity_data = {
            "actor": user['user_id'] , 
            "verb": "ship", 
            "object": "Place:42",
            "arrival" : new_shipment.arrival,
            "description": new_shipment.description,
            "destination": new_shipment.destination,
            "source": new_shipment.source,
            "item": new_shipment.item,
            "status": new_shipment.status,
            "tracking_number": new_shipment.tracking_number
            }

            user_feed.add_activity(activity_data)
            return shipment_schema.jsonify(new_shipment)
        except Exception as e:
            return jsonify(e)
        

    def put(self, id):
        """
        Update shipment
        """
        try:
            
            data = request.get_json()

            if data.get("headers").get("Authorization"):
            
                token = data['headers']['Authorization']   
                
                # decode token
                user = jwt.decode(token[7:], STREAM_SECRET_KEY)

                # Instantiate a feed object
                user_feed = client.feed('user', user['user_id'])

                del data['headers']

                shipment = Shipment.query.filter_by(id=id)
                shipment.update(data)
                db.session.commit()
                
                activity_data = {
                "actor": user['user_id'] , 
                "verb": "ship", 
                "object": "Place:42",
                }

                activity_data.update(data)

                user_feed.add_activity(activity_data)
                return jsonify(data)

        except Exception as e:
            print(e)
            return { "message": "Error updating shipment"}

# Routes
api.add_resource(GenerateToken, '/generate-token')
api.add_resource(ShipmentView, '/shipment/', '/shipment/<int:id>' )

if __name__ == '__main__':
    app.run(debug=True)


