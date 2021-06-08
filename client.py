import requests
import matplotlib.pyplot as plt
import pandas as pd
from scipy.signal import find_peaks
from scipy import interpolate
import numpy as np


class Client:

    # class variables
    step_size_for_spline_interpolation = 0.5

    def __init__(self, rolling_val, max_prominence_val, min_prominence_val):
        self.rolling_val = rolling_val                  # rollin_val = window size for smoothing
        self.max_prominence_val = max_prominence_val    # max_prominence_val = threshold for
        self.min_prominence_val = min_prominence_val
        self.peak_pos = []
        self.peak_height = []
        self.min_pos = []
        self.min_height = []
        self.x_for_spline = []
        self.y_for_spline = []


    def data_preparation_pandas(self, list_of_db_entries):
        df = pd.DataFrame(list_of_db_entries)
        df['datetime'] = pd.to_datetime(df['time_of_collection'])
        # datetime to float transformation for convenience
        df['hour'] = df['datetime'].dt.hour
        df['minute'] = df['datetime'].dt.minute
        df['time_of_day_index'] = df['hour'] + df['minute']/60
        if self.rolling_val <= 1:
            df['smoothed_eta'] = df['ETA']
        else:
            df['smoothed_eta'] = df['ETA'].rolling(self.rolling_val).mean()
        df['eta_first_derivative'] = df['smoothed_eta'].diff()
        df['eta_second_derivative'] = df['eta_first_derivative'].diff()
        new_df = df.sort_values(['hour', 'minute'])
        new_df = new_df.reset_index()
        return new_df


    def plot_eta_from_pandas(self, df):
        self.find_local_max_min(df)
        time_of_day_index_x = df['time_of_day_index'].to_numpy()
        smoothed_eta_y = df['smoothed_eta'].to_numpy()
        self.do_spline_interpolation(df)
        plt.plot(time_of_day_index_x, smoothed_eta_y, '-', self.x_for_spline, self.y_for_spline, '--',)
        plt.scatter(self.peak_pos, self.peak_height, marker='X', c='r')
        plt.scatter(self.min_pos, self.min_height, marker='X', c='g')
        plt.xlim([0, 24])
        plt.locator_params(axis="x", nbins=24)
        plt.title('ETA vs. time of day')
        plt.xlabel('Time of day')
        plt.ylabel('ETA (min)')
        plt.legend(['data', 'cubic spline'], loc='best')
        plt.show()


    def do_spline_interpolation(self, df):
        start_point = df.loc[df['time_of_day_index'].idxmin()]      # find min time of day point - get x, y for spline graph
        start_point_time_of_day_index = start_point['time_of_day_index']
        start_point_eta = start_point['ETA']
        end_point = df.loc[df['time_of_day_index'].idxmax()]    # find max time of day point - get x, y for spline graph
        end_point_time_of_day_index = end_point['time_of_day_index']
        end_point_eta = end_point['ETA']

        # vals for spline = peaks, minima, start point, end point
        x_axis_for_spline = np.concatenate((self.peak_pos, self.min_pos, start_point_time_of_day_index, end_point_time_of_day_index),
                                           axis=None)
        y_axis_for_spline = np.concatenate((self.peak_height, self.min_height, start_point_eta, end_point_eta), axis=None)
        sorted_x_axis_for_spline, sorted_y_axis_for_spline = (list(t) for t in
                                                              zip(*sorted(zip(x_axis_for_spline, y_axis_for_spline))))

        # calculating spline representation
        tck = interpolate.splrep(sorted_x_axis_for_spline, sorted_y_axis_for_spline, s=0)
        step_size = self.step_size_for_spline_interpolation
        self.x_for_spline = np.arange(0, 24.001, step_size)  # + 0.001 addition due to floating point precision
        self.y_for_spline = interpolate.splev(self.x_for_spline, tck, der=0)


    def find_local_max_min(self, df):
        time_of_day_index_x = df['time_of_day_index'].to_numpy()
        smoothed_eta_y_max = df['smoothed_eta'].to_numpy()  # for finding local maxima
        peaks = find_peaks(smoothed_eta_y_max, height=0, prominence=self.max_prominence_val)
        self.peak_pos = time_of_day_index_x[peaks[0]]
        self.peak_height = peaks[1]['peak_heights']

        smoothed_eta_y_min = smoothed_eta_y_max * -1  # for finding local minima
        minima = find_peaks(smoothed_eta_y_min, prominence=self.min_prominence_val)
        self.min_pos = time_of_day_index_x[minima[0]]
        min_height = smoothed_eta_y_min[minima[0]]
        self.min_height = min_height * -1



BASE = "http://127.0.0.1:5000/"


response1 = requests.get(BASE + "route/rosh haayin, amal 10/tel aviv, j.l. gordon 61")
resp1_json = response1.json()
client = Client(20, 1.5, 0.5)
df = client.data_preparation_pandas(resp1_json)
client.plot_eta_from_pandas(df)
