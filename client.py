import requests
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
from scipy.signal import find_peaks
from scipy import interpolate
import numpy as np
from tkinter import *
from tkinter import ttk
from datetime import datetime


class Client:

    # class variables
    num_of_points_for_splrep = 50
    num_of_points_for_splev = 150

    def __init__(self, rolling_val, max_prominence_val, min_prominence_val):
        self.rolling_val = rolling_val                  # rollin_val = window size for smoothing
        self.max_prominence_val = max_prominence_val    # max_prominence_val = threshold for local maxima finding
        self.min_prominence_val = min_prominence_val    # min_prominence_val = threshold for local minima finding
        self.desired_driving_time = 0
        self.peak_pos = []
        self.peak_height = []
        self.peak_height_no_smoothing = []
        self.min_pos = []
        self.min_height = []
        self.min_height_no_smoothing = []
        self.x_for_spline = []
        self.y_for_spline = []
        self.source = 'tel aviv, j.l. gordon 61'    # temp default val
        self.destination = 'rosh haayin, amal 10'   # temp default val
        self.base_address = "http://127.0.0.1:5000/"
        self.opening_window = self.create_opening_window()
        self.route_data_from_db = {}
        self.eta_and_time_index_now = []


    def create_opening_window(self):
        self.opening_window = Tk()
        self.opening_window.title("Traffic jam analyzer")
        self.opening_window.iconbitmap('./icon5.ico')

        # UI - input boxes
        source_description = Label(self.opening_window, text="Enter source: ")
        source_description.grid(row=0, column=0, sticky='w')
        destination_description = Label(self.opening_window, text="Enter destination: ")
        destination_description.grid(row=1, column=0, sticky='w')
        source = Entry(self.opening_window, width=25)
        destination = Entry(self.opening_window, width=25)
        source.grid(row=0, column=1)
        destination.grid(row=1, column=1)
        source.insert(0, "{}".format(self.source))    # TODO: add restriction on the amount of chars
        destination.insert(0, "{}".format(self.destination))    # TODO: add restriction on the amount of chars

        # UI - separator
        self.opening_window.grid_columnconfigure(2, minsize=5)
        separator = ttk.Separator(self.opening_window, orient='vertical')
        separator.grid(row=0, column=2, rowspan=60, sticky="ns")

        # UI - define sliders
        smoothing_factor = Scale(self.opening_window, from_=1, to=100, length=150, orient=HORIZONTAL)
        max_prominence_val_factor = Scale(self.opening_window, from_=0.5, to=5.0, length=150, resolution=0.1, orient=HORIZONTAL)
        min_prominence_val_factor = Scale(self.opening_window, from_=0.5, to=5.0, length=150, resolution=0.1, orient=HORIZONTAL)
        desired_driving_time = Scale(self.opening_window, from_=30, to=60, length=150, orient=HORIZONTAL)

        # UI - waiting time message
        text_for_waiting_time_label = "tmp" # TODO: find a better way
        waiting_time_label = Label(self.opening_window, text=text_for_waiting_time_label, font=('Helvatical bold', 16))

        """# UI - check box TODO: add dark theme functionality
        dark_mode_var = IntVar()
        dark_mode_check_box = Checkbutton(self.opening_window, text="Dark mode (TBD)", variable=dark_mode_var)
        dark_mode_check_box.grid(row=59, column=0)"""

        # UI - button functions
        def send_add_route_request():
            self.source = source.get()
            self.destination = destination.get()
            response = requests.put(self.base_address + "route/{}/{}".format(self.source, self.destination))
            response_json = response.json()
            add_route_window = Tk()
            response_message = Label(add_route_window, text='{}'.format(response_json))
            response_message.pack()
            ok_button = Button(add_route_window, text='OK', command=add_route_window.destroy)
            ok_button.pack()

        def display_route_data():
            self.source = source.get()
            self.destination = destination.get()
            if self.source == "" or self.destination == "":
                display_route_message_window = Tk()
                message = "Input missing. Please enter a valid route"
                response_message = Label(display_route_message_window, text=message)
                response_message.pack()
                ok_button = Button(display_route_message_window, text='OK',
                                   command=display_route_message_window.destroy)
                ok_button.pack()
            else:
                response = requests.get(self.base_address + "route/{}/{}".format(self.source, self.destination))
                response_json = response.json()
                # check if a route doesn't exist in DB or is invalid
                if len(response_json[0]) < 200:
                    display_route_message_window = Tk()
                    response_message = Label(display_route_message_window, text='{}'.format(response_json))
                    response_message.pack()
                    ok_button = Button(display_route_message_window, text='OK', command=display_route_message_window.destroy)
                    ok_button.pack()
                else:                   # route exists in DB and is ready for display
                    self.route_data_from_db = response_json[0]
                    eta_at_time_of_request = response_json[1]
                    datetime_at_time_of_request = datetime.now()
                    hour_at_time_of_request = datetime_at_time_of_request.hour
                    minute_at_time_of_request = datetime_at_time_of_request.minute
                    time_of_day_index = self.time_to_time_of_day_index(hour_at_time_of_request, minute_at_time_of_request)
                    self.eta_and_time_index_now = [time_of_day_index, eta_at_time_of_request]
                    sorted_df = self.data_preparation_pandas()
                    self.do_spline_interpolation_constant_intervals(sorted_df)  # spline calculation (done once)
                    self.plot_eta_from_pandas_tkinter_embedded(sorted_df, self.eta_and_time_index_now)

                    start_point = sorted_df.loc[sorted_df['ETA'].idxmin()]
                    start_point_eta = start_point['ETA']
                    end_point = sorted_df.loc[sorted_df['ETA'].idxmax()]
                    end_point_eta = end_point['ETA']
                    end_point_start_point_diff = end_point_eta - start_point_eta
                    offset_for_desired_driving_time_set_point = 0.25 * end_point_start_point_diff
                    self.desired_driving_time = start_point_eta + offset_for_desired_driving_time_set_point

                    desired_driving_time.config(from_=start_point_eta, to=end_point_eta)

                    # UI - display sliders
                    self.opening_window.geometry("878x400")
                    slider_row = 15
                    smoothing_factor.grid(row=slider_row, column=1)
                    smoothing_factor.set(20)
                    max_prominence_val_factor.grid(row=slider_row+1, column=1)
                    max_prominence_val_factor.set(1.5)
                    min_prominence_val_factor.grid(row=slider_row+2, column=1)
                    min_prominence_val_factor.set(1.0)
                    desired_driving_time.grid(row=slider_row+3, column=1)
                    desired_driving_time.set(self.desired_driving_time)


                    # UI - slider labels
                    smoothing_factor_description = Label(self.opening_window, text="Smoothing factor")
                    smoothing_factor_description.grid(row=slider_row, column=0, sticky='w')
                    max_prominence_description = Label(self.opening_window, text="Prominence value\n (local maxima)")
                    max_prominence_description.grid(row=slider_row+1, column=0, sticky='w')
                    min_prominence_description = Label(self.opening_window, text="Prominence value\n (local minima)")
                    min_prominence_description.grid(row=slider_row+2, column=0, sticky='w')
                    desired_driving_time_description = Label(self.opening_window, text="Desired driving time")
                    desired_driving_time_description.grid(row=slider_row+3, column=0, sticky='w')


                    # UI - button
                    update_plot_button = Button(self.opening_window, text='Update plot', command=get_values_for_updated_plot)
                    update_plot_button.grid(row=slider_row+4, column=1)

                    # finding first time that is <= threshold
                    # TODO: put in a separate func
                    time_of_day_index_now = self.eta_and_time_index_now[0]
                    eta_now = self.eta_and_time_index_now[1]
                    text_for_waiting_time_label = ""
                    if eta_now <= self.desired_driving_time:
                        text_for_waiting_time_label = "Leave now"
                    else:
                        for idx, row in sorted_df[sorted_df['time_of_day_index'] > time_of_day_index_now].iterrows():
                            if sorted_df.iloc[idx, 10] <= self.desired_driving_time:  # 10 - smoothed ETA
                                datetime_at_threshold_str = sorted_df.iloc[idx, 5][17:22]
                                text_for_waiting_time_label = "Leave at {}".format(datetime_at_threshold_str)
                                break

                    # UI - waiting time message
                    waiting_time_label.grid_forget()
                    waiting_time_label.config(text=text_for_waiting_time_label) # TODO: split str to 2 cols
                    waiting_time_label.grid(row=slider_row+5, column=0)


        def get_values_for_updated_plot():
            self.rolling_val = smoothing_factor.get()
            self.max_prominence_val = max_prominence_val_factor.get()
            self.min_prominence_val = min_prominence_val_factor.get()
            self.desired_driving_time = desired_driving_time.get()
            sorted_df = self.data_preparation_pandas()
            self.plot_eta_from_pandas_tkinter_embedded(sorted_df, self.eta_and_time_index_now)

            # finding first time that is <= threshold
            # TODO: put in a separate func
            time_of_day_index_now = self.eta_and_time_index_now[0]
            eta_now = self.eta_and_time_index_now[1]
            text_for_waiting_time_label = ""
            if eta_now <= self.desired_driving_time:
                text_for_waiting_time_label = "Leave now"
            else:
                for idx, row in sorted_df[sorted_df['time_of_day_index'] > time_of_day_index_now].iterrows():
                    if sorted_df.iloc[idx, 10] <= self.desired_driving_time:        # 10 - smoothed ETA
                        datetime_at_threshold_str = sorted_df.iloc[idx, 5][17:22]
                        text_for_waiting_time_label = "Leave at {}".format(datetime_at_threshold_str)
                        break


            # UI - waiting time message
            waiting_time_label.grid_forget()
            waiting_time_label.config(text=text_for_waiting_time_label) # TODO: split str to 2 cols
            waiting_time_label.grid(row=20, column=0)


        # UI - Buttons
        add_route_to_control_db = Button(self.opening_window, text='Add route', command=send_add_route_request)
        add_route_to_control_db.grid(row=2, column=0, pady=10)
        display_route_data = Button(self.opening_window, text='Display data', command=display_route_data)
        display_route_data.grid(row=2, column=1, pady=10)

        def on_closing():
            self.opening_window.quit()
            self.opening_window.destroy()

        self.opening_window.protocol("WM_DELETE_WINDOW", on_closing)
        self.opening_window.mainloop()


    def time_to_time_of_day_index(self, hour, minute):
        time_of_day_index = hour + minute/60
        return time_of_day_index


    def smoothing_function(self, df):
        if self.rolling_val <= 1:
            df['smoothed_eta'] = df['ETA']
        else:
            df['smoothed_eta'] = df['ETA'].rolling(self.rolling_val, min_periods=1).mean()


    def data_preparation_pandas(self):
        df = pd.DataFrame(self.route_data_from_db)
        df['datetime'] = pd.to_datetime(df['time_of_collection'])
        # datetime to float transformation for convenience
        df['hour'] = df['datetime'].dt.hour
        df['minute'] = df['datetime'].dt.minute
        df['time_of_day_index'] = df['hour'] + df['minute']/60
        self.smoothing_function(df)
        sorted_df = df.sort_values(['hour', 'minute'])
        sorted_df = sorted_df.reset_index()
        return sorted_df

    # func uses every k-th point of the ETA vs. time of day graph
    def do_spline_interpolation_constant_intervals(self, df):
        start_point = df.loc[df['time_of_day_index'].idxmin()]  # find min time of day point - get x, y for spline graph
        start_point_time_of_day_index = start_point['time_of_day_index']
        start_point_eta = start_point['ETA']
        end_point = df.loc[df['time_of_day_index'].idxmax()]  # find max time of day point - get x, y for spline graph
        end_point_time_of_day_index = end_point['time_of_day_index']
        end_point_eta = end_point['ETA']

        splrep_step_size = len(df) // self.num_of_points_for_splrep

        start_point_for_iloc = splrep_step_size
        x_axis_for_spline = df.iloc[start_point_for_iloc::splrep_step_size, 9].to_numpy()
        y_axis_for_spline = []
        for item in x_axis_for_spline:
            curr_eta = df.loc[df['time_of_day_index'] == item, 'ETA'].values[0]
            y_axis_for_spline.append(curr_eta)

        # adding start and end points to the vals for spline
        full_x_axis_for_spline = np.concatenate((start_point_time_of_day_index, x_axis_for_spline,
                                                 end_point_time_of_day_index),axis=None)
        full_y_axis_for_spline = np.concatenate((start_point_eta, y_axis_for_spline, end_point_eta), axis=None)

        # calculating spline representation
        tck = interpolate.splrep(full_x_axis_for_spline, full_y_axis_for_spline, s=0)

        splev_step_size = 24 / self.num_of_points_for_splev
        self.x_for_spline = np.arange(0, 24.001, splev_step_size)  # + 0.001 addition due to floating point precision
        self.y_for_spline = interpolate.splev(self.x_for_spline, tck, der=0)

    # func uses local minima and maxima of the ETA vs. time of day graph
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
        y_axis_for_spline = np.concatenate((self.peak_height_no_smoothing, self.min_height_no_smoothing, start_point_eta,
                                            end_point_eta), axis=None)
        sorted_x_axis_for_spline, sorted_y_axis_for_spline = (list(t) for t in
                                                              zip(*sorted(zip(x_axis_for_spline, y_axis_for_spline))))

        # calculating spline representation
        tck = interpolate.splrep(sorted_x_axis_for_spline, sorted_y_axis_for_spline, s=0)
        step_size = 24 / self.num_of_points_for_splev
        self.x_for_spline = np.arange(0, 24.001, step_size)  # + 0.001 addition due to floating point precision
        self.y_for_spline = interpolate.splev(self.x_for_spline, tck, der=0)


    def find_local_max_min(self, df):
        # self.peak_height_no_smoothing, self.min_height_no_smoothing are not empty if function executes more than 1 time
        # per run
        self.peak_height_no_smoothing = []
        self.min_height_no_smoothing = []
        time_of_day_index_x = df['time_of_day_index'].to_numpy()
        smoothed_eta_y_max = df['smoothed_eta'].to_numpy()  # for finding local maxima
        peaks = find_peaks(smoothed_eta_y_max, height=0, prominence=self.max_prominence_val)
        self.peak_pos = time_of_day_index_x[peaks[0]]
        self.peak_height = peaks[1]['peak_heights']
        for item in self.peak_pos:
            curr_eta = df.loc[df['time_of_day_index'] == item, 'ETA'].values[0]
            self.peak_height_no_smoothing.append(curr_eta)

        smoothed_eta_y_min = smoothed_eta_y_max * -1  # for finding local minima
        minima = find_peaks(smoothed_eta_y_min, prominence=self.min_prominence_val)
        self.min_pos = time_of_day_index_x[minima[0]]
        min_height = smoothed_eta_y_min[minima[0]]
        self.min_height = min_height * -1
        for item in self.min_pos:
            curr_eta = df.loc[df['time_of_day_index'] == item, 'ETA'].values[0]
            self.min_height_no_smoothing.append(curr_eta)

    # func receives sorted df
    def plot_eta_from_pandas_tkinter_embedded(self, df, eta_and_time_index_now):
        self.find_local_max_min(df)
        time_of_day_index_x = df['time_of_day_index'].to_numpy()
        smoothed_eta_y = df['smoothed_eta'].to_numpy()
        #eta = df['ETA'].to_numpy()
        figure = plt.figure(figsize=(6, 4), dpi=100)
        time_index_now = eta_and_time_index_now[0]
        eta_now = eta_and_time_index_now[1]
        figure.add_subplot(111).plot(time_of_day_index_x, smoothed_eta_y, '-', self.x_for_spline, self.y_for_spline, '--')
        plt.plot(time_index_now, eta_now, 'om', label='eta now')
        plt.scatter(self.peak_pos, self.peak_height, marker='X', c='r', label='local maxima')
        plt.scatter(self.min_pos, self.min_height, marker='X', c='g', label='local minima')
        plt.legend(['data', 'cubic spline', 'Travel time now', 'local maxima', 'local minima'], scatterpoints=1, loc='upper left')
        if self.desired_driving_time == 0:
            start_point = df.loc[df['ETA'].idxmin()]
            start_point_eta = start_point['ETA']
            end_point = df.loc[df['ETA'].idxmax()]
            end_point_eta = end_point['ETA']
            end_point_start_point_diff = end_point_eta - start_point_eta
            offset_for_desired_driving_time_set_point = 0.25 * end_point_start_point_diff
            self.desired_driving_time = start_point_eta + offset_for_desired_driving_time_set_point
        for i in range(len(time_of_day_index_x)-1):
            if smoothed_eta_y[i] <= self.desired_driving_time:
                plt.axvspan(time_of_day_index_x[i], time_of_day_index_x[i+1], facecolor='g', alpha=0.3)
            elif smoothed_eta_y[i] > self.desired_driving_time:
                plt.axvspan(time_of_day_index_x[i], time_of_day_index_x[i+1], facecolor='r', alpha=0.4)
        chart = FigureCanvasTkAgg(figure, self.opening_window)
        chart.get_tk_widget().grid(row=0, column=3, rowspan=60)
        plt.xlim([0, 24])
        plt.locator_params(axis="x", nbins=24)
        plt.title('Travel time vs. time of day')
        plt.xlabel('Time of day')
        plt.ylabel('Travel time (min)')


smoothing_val_default = 20
max_prominence_val_default = 1.5
min_prominence_val_default = 1.0
client = Client(smoothing_val_default, max_prominence_val_default, min_prominence_val_default)
