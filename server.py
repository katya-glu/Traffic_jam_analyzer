from flask import Flask
from flask_restful import Api, Resource, reqparse, fields, marshal_with, abort
from flask_sqlalchemy import SQLAlchemy
import WazeRouteCalculator
from datetime import datetime
import schedule
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
    READY_THRESHOLD = 500

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


"""video_update_args = reqparse.RequestParser()
video_update_args.add_argument("name", type=str, help="Name of the video required")
video_update_args.add_argument("views", type=int, help="Views of the video required")
video_update_args.add_argument("likes", type=int, help="Likes of the video required")"""

resource_fields = {
    "id": fields.Integer,
    "source": fields.String,
    "destination": fields.String,
    "status": fields.Integer,
    "num_of_measurements": fields.Integer,
}


class MapServerInterface:
    def __init__(self):
        self.valid_routes_cache = self.create_valid_routes_cache_for_sample_gathering()
        #print(self.valid_routes_cache)

    def create_valid_routes_cache_for_sample_gathering(self):
        routes_cache = {}
        routes_in_ctrl_db = ControlDatabaseModel.query.all()
        for route in routes_in_ctrl_db:
            if route.status != ControlDatabaseModel.READY and route.status != ControlDatabaseModel.INVALID:
                num_of_remaining_measurements = ControlDatabaseModel.READY_THRESHOLD - route.num_of_measurements
                routes_cache[(route.source, route.destination)] = num_of_remaining_measurements
        return routes_cache

    def collect_data_from_map_service(self):
        t = TicToc()
        while len(self.valid_routes_cache) > 0:
            start_time = time.time()
            for key, value in self.valid_routes_cache.copy().items():
                #print(self.valid_routes_cache.items())
                if self.valid_routes_cache[key] == 0:
                    del self.valid_routes_cache[key]
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
                    #db.session.commit()
                    print(eta_measurement)
                    print(route)
                    print("Num of active threads is {}".format(threading.activeCount()))

            #t.tic()
            db.session.commit()
            #t.toc('Section 6 took')

            end_time = time.time()
            time_to_sleep = 60 - (end_time - start_time)
            time.sleep(time_to_sleep)

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


    def print_control_db_queries(self):
        routes_in_ctrl_db = ControlDatabaseModel.query.all()
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        print("Current Time =", current_time)
        for route in routes_in_ctrl_db:
            print("ID = {}".format(route.id), "|", "Source = {}".format(route.source), "|",
                  "Destination = {}".format(route.destination), "|", "Status = {}".format(route.status), "|",
                  "Num of measurements = {}".format(route.num_of_measurements))


    def scheduling_func(self):
        schedule.every(10).seconds.do(self.print_control_db_queries)
        while True:
            now = datetime.now()
            if now.hour >= 8 and now.hour < 20:
            #if now.minute >= 20 and now.minute < 21:
                schedule.run_pending()




class Route(Resource):
    def __init__(self):
        self.id_of_last_entry_in_control_db = self.get_id_of_last_entry()

    def get_id_of_last_entry(self):
        all_entries = ControlDatabaseModel.query.all()  # TODO: save curr last id to file
        if len(all_entries) > 0:
            id_of_last_entry = all_entries[-1].id
            return id_of_last_entry
        else:
            return len(all_entries)


    def get(self, source, destination):
        lower_source = source.lower()
        lower_destination = destination.lower()
        result = ControlDatabaseModel.query.filter_by(source=lower_source, destination=lower_destination).first()


        if not result:
            if self.is_valid_route(source, destination):
                route = ControlDatabaseModel(source=lower_source, destination=lower_destination,
                                             status=ControlDatabaseModel.NOT_READY,
                                             num_of_measurements=0)
                message = "The route was successfully added to DB. ETA data will be available at a later date" # TODO: change message?
            else:
                route = ControlDatabaseModel(source=lower_source, destination=lower_destination,
                                             status=ControlDatabaseModel.INVALID,
                                             num_of_measurements=0)
                message = "The route does not exist. Please enter a valid route"

            db.session.add(route)
            db.session.commit()
            return message, 201

        elif result.status == ControlDatabaseModel.INVALID:
            message = "The route does not exist. Please enter a valid route"
            return message, 201

    def put(self, source, destination):
        lower_source = source.lower()
        lower_destination = destination.lower()
        result = ControlDatabaseModel.query.filter_by(source=lower_source, destination=lower_destination).first()
        already_in_db_message = "The route was already added"
        if not result:
            #curr_route_id = self.id_of_last_entry_in_control_db + 1
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
            #self.id_of_last_entry_in_control_db += 1
            db.session.add(route)
            db.session.commit()
            return message, 201
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


api.add_resource(Route, "/route/<string:source>/<string:destination>")

if __name__ == '__main__':
    server = MapServerInterface()
    """with concurrent.futures.ThreadPoolExecutor() as executor:
        valid_routes_cache_list = list(server.valid_routes_cache)
        executor.map(server.collect_data_from_map_service, valid_routes_cache_list)"""

    thread = threading.Thread(target=server.collect_data_from_map_service)
    thread.start()
    #print(threading.activeCount())
    #server.collect_data_from_map_service()
    app.run(debug=False)


