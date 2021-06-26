from flask import Flask
from flask_restful import Api, Resource, fields, marshal
from flask_sqlalchemy import SQLAlchemy
import WazeRouteCalculator
from datetime import datetime
import time
import threading
from pytictoc import TicToc
import concurrent.futures

app = Flask(__name__)
api = Api(app)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///database.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app, session_options={"autoflush": False})


class ControlDatabaseModel(db.Model):

    # status enumerators
    NOT_READY = 0
    READY = 2
    INVALID = 3

    # num of samples for entry to be considered ready for display
    READY_THRESHOLD = 1440

    # PyCharm code inspection issue:
    # (https://stackoverflow.com/questions/35242153/unresolved-attribute-column-in-class-sqlalchemy)
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    status = db.Column(db.Integer, nullable=False)
    num_of_measurements = db.Column(db.Integer, nullable=False)


class ETADatabaseModel(db.Model):

    # PyCharm code inspection issue:
    # (https://stackoverflow.com/questions/35242153/unresolved-attribute-column-in-class-sqlalchemy)
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    ETA = db.Column(db.Integer, nullable=False)
    time_of_collection = db.Column(db.DateTime, nullable=False)

#db.create_all()       # use this line after deleting database.db

resource_fields = {
    "id": fields.Integer,
    "source": fields.String,
    "destination": fields.String,
    "ETA": fields.Integer,
    "time_of_collection": fields.DateTime,
}


class MapServerInterface:
    def __init__(self, debug_mode_data_collection):
        self.valid_routes_cache = self.create_valid_routes_cache_for_sample_gathering()
        if type(debug_mode_data_collection) is bool:
            self.debug_mode_data_collection = debug_mode_data_collection
        else:
            self.debug_mode_data_collection = True              # default is to collect data


    def create_valid_routes_cache_for_sample_gathering(self):
        routes_cache = {}
        routes_in_ctrl_db = ControlDatabaseModel.query.all()
        for route in routes_in_ctrl_db:
            if route.status != ControlDatabaseModel.READY and route.status != ControlDatabaseModel.INVALID:
                num_of_remaining_measurements = ControlDatabaseModel.READY_THRESHOLD - route.num_of_measurements
                routes_cache[(route.source, route.destination)] = num_of_remaining_measurements
        return routes_cache


    # for unit testing of routes addition to DB (if not deleted, a route can be added only once)
    def delete_route_from_ControlDB(self, source, destination):
        lower_source = source.lower()
        lower_destination = destination.lower()
        ControlDatabaseModel.query.filter_by(source=lower_source, destination=lower_destination).delete()
        db.session.commit()


    def collect_data_from_map_service(self):
        print('Data collection has started')
        t = TicToc()
        while len(self.valid_routes_cache) > 0:
            start_time = time.time()
            for key, value in self.valid_routes_cache.copy().items():
                #print(self.valid_routes_cache.items())
                if self.valid_routes_cache[key] == 0:
                    del self.valid_routes_cache[key] # TODO: add status change
                else:
                    #t.tic()
                    source = key[0]
                    destination = key[1]
                    #t.tic()
                    ETA = self.get_route_info(source, destination)
                    #t.toc('Section 1 took', restart=True)
                    time_of_collection = datetime.now()
                    #t.toc('Section 2 took', restart=True)
                    eta_measurement = ETADatabaseModel(source=source, destination=destination, ETA=ETA,
                                                       time_of_collection=time_of_collection)
                    #t.toc('Section 3 took', restart=True)
                    self.valid_routes_cache[key] -= 1
                    route = ControlDatabaseModel.query.filter_by(source=source, destination=destination).first()
                    #t.toc('Section 4 took', restart=True)
                    route.num_of_measurements += 1

                    db.session.add(eta_measurement)
                    #t.toc('Section 5 took', restart=True)
                    #print("Num of active threads is {}".format(threading.activeCount()))

            #t.tic()
            db.session.commit()
            #t.toc('Commit took')

            end_time = time.time()
            time_to_sleep = 60 - (end_time - start_time)
            time.sleep(time_to_sleep)


    # preparation for ThreadPool functionality
    """def collect_data_from_map_service(self, key):
        while self.valid_routes_cache[key]:
            start_time = time.time()
            #for key, value in self.valid_routes_cache.copy().items():
            if self.valid_routes_cache[key] == 0:
                del self.valid_routes_cache[key]
            else:
                source = key[0]
                destination = key[1]
                ETA = self.get_route_info(source, destination)
                time_of_collection = datetime.now()
                eta_measurement = ETADatabaseModel(source=source, destination=destination, ETA=ETA,
                                                   time_of_collection=time_of_collection)
                self.valid_routes_cache[key] -= 1
                route = ControlDatabaseModel.query.filter_by(source=source, destination=destination).first()
                route.num_of_measurements += 1

                db.session.add(eta_measurement)
                print(eta_measurement)
                print(route)
                print("Num of active threads is {}".format(threading.activeCount()))

            db.session.commit()

            end_time = time.time()
            time_to_sleep = 60 - (end_time - start_time)
            time.sleep(time_to_sleep)"""


    def get_route_info(self, source, destination):
        from_address = source
        to_address = destination
        region = 'IL'
        route = WazeRouteCalculator.WazeRouteCalculator(from_address, to_address, region)
        route_info = route.calc_route_info()
        eta = route_info[0]
        return eta


class Route(Resource):

    def get(self, source, destination):
        lower_source = source.lower()
        lower_destination = destination.lower()
        result = ControlDatabaseModel.query.filter_by(source=lower_source, destination=lower_destination).first()

        if not result:
            message = "The route is not in the database. Please add the route"
            return message
        elif result.status == ControlDatabaseModel.INVALID:
            message = "The route does not exist. Please enter a valid route"
            return message
        else: # TODO: add check if status is 'READY'
            query = ETADatabaseModel.query.filter_by(source=lower_source, destination=lower_destination).all()
            updated_query = marshal(query, resource_fields)
            eta_at_time_of_request = self.get_route_info(source, destination)
            return [updated_query, eta_at_time_of_request]


    def put(self, source, destination):
        lower_source = source.lower()
        lower_destination = destination.lower()
        result = ControlDatabaseModel.query.filter_by(source=lower_source, destination=lower_destination).first()
        already_in_db_message = "The route was already added"
        if not result:
            if self.is_valid_route(source, destination):
                route = ControlDatabaseModel(source=lower_source, destination=lower_destination,
                                             status=ControlDatabaseModel.NOT_READY,
                                             num_of_measurements=0)
                message = "The route was successfully added to DB"
            else:
                route = ControlDatabaseModel(source=lower_source, destination=lower_destination,
                                             status=ControlDatabaseModel.INVALID,
                                             num_of_measurements=0)
                message = "The route does not exist. Please enter a valid route"
            db.session.add(route)
            db.session.commit()
            return message
        return already_in_db_message


    def is_valid_route(self, source, destination):
        from_address = source
        to_address = destination
        region = 'IL'
        try:
            route = WazeRouteCalculator.WazeRouteCalculator(from_address, to_address, region)
            return True
        except WazeRouteCalculator.WRCError:
            return False


    def get_route_info(self, source, destination):
        from_address = source
        to_address = destination
        region = 'IL'
        route = WazeRouteCalculator.WazeRouteCalculator(from_address, to_address, region)
        route_info = route.calc_route_info()
        eta = route_info[0]
        return eta


api.add_resource(Route, "/route/<string:source>/<string:destination>")

if __name__ == '__main__':
    server = MapServerInterface(True)
    # preparation for ThreadPool functionality
    """with concurrent.futures.ThreadPoolExecutor() as executor:
        valid_routes_cache_list = list(server.valid_routes_cache)
        executor.map(server.collect_data_from_map_service, valid_routes_cache_list)"""

    if server.debug_mode_data_collection:
        thread = threading.Thread(target=server.collect_data_from_map_service)
        thread.start()
    app.run(debug=False)


