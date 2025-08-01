# This module is to define Producer class
import csv
from calendar import prmonth

class Producer:

    # Define class point to contain specific value for each point
    class Point:

        def __init__(self, slot, prod):
            # Timestamp of the slot
            self.slot = slot
            # Consumer consumption for the slot
            self.prod = prod
            
    def __init__(self, name, prm, file = None):
        self.name = name
        # Point Reference Mesure: uniquely identify the producer
        self.prm = prm
        # List of points for each slot of 15 min
        self.point_list = []
        if file is not None:
            self.read_production(file)

    # This function reads a file to set production values
    def read_production(self, file):
        with open(file, newline='') as csvfile:
            next(csvfile) # Skip first line of the file which contains title
            prod_file = csv.reader(csvfile,delimiter=';')
            for row in prod_file:
                self.point_list.append(Producer.Point(row[0], float(row[1].replace(',','.'))))
                # print(row)
            print('Producer file read!')

    # This function reads a stream
    # def read_stream(self, stream):
    #     prod_file = csv.reader(stream,delimiter=';')
    #     for row in prod_file:
    #         try:
    #             self.point_list.append(Producer.Point(row[0], float(row[1].replace(',','.'))))
    #         except ValueError as e:
    #             print('Erreur')
    #         #print(row)
    #     print('Stream read!')

    # This function apply a factor to the initial production.
    # This is useful to get statistic with lower production
    def apply_factor(self, factor):
        for point in self.point_list:
            point.prod *= factor