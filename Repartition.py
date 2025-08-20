# This module is to define Repartition class
import csv
import logging
import math

from datetime import datetime

# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

EXPORT_FOLDER = 'Export\\'

# The following class defines the strategy to compute repartition keys
class Strategy:
    # DYNAMIC_BY_DEFAULT compute repartition keys based on consumption value of each consumers
    # This is the strategy used by default by ENEDIS at the time of writing
    DYNAMIC_BY_DEFAULT = 1
    # DYNAMIC compute repartition keys based on priority and ratio defined for each customer
    # It is also optimized to dispatch remaining consumption (when there is) to the consumers
    # that still have consumption after applying priority and ratio.
    # This allow to limit waste of production and to have the same efficiency as  DYNAMIC_BY_DEFAULT
    DYNAMIC = 2
    # STATIC compute using static ration. Due to low efficiency it is not implemented yet.
    # MAy be implemented later for study purpose
    STATIC = 3


# The following class describes the different states a consumer can have
class State:
    # ACTIVE is the default state.
    # Consumer is used to compute repartition key
    ACTIVE = 1
    # A consumer is INACTIVE when all possible production has been used fot the iteration
    # but its consumption is still not filled
    # Consumer is not used to compute repartition key for the current iteration
    INACTIVE = 2
    # A consumer is COMPLETE when all its consumption has been filled
    # Consumer is not anymore used to compute repartition key for the current time slot
    COMPLETE = 3

class Repartition:

    # Class to contain specific information for each point
    class Point:

        # Class containing producer information to compute repartition keys
        class ProdRepart:
            def __init__(self, initial_production):
                self.initial_production = initial_production
                self.production = initial_production
                self.prod_to_remove = 0

        # Class describing repartition keys for all consumers for a specific slot
        class ConsRepart:
            class Param:
                def __init__(self, priority, ratio):
                    # Consumption from autocollect
                    self.auto_consumption = 0
                    # List of priorities for each consumer
                    self.priority = priority
                    # List representing key and intermediate ratio computed for each producer
                    self.key = ratio

            def __init__(self, consumption, priority_list, ratio_list):
                # Represents state of the consumer
                self.state = State.ACTIVE
                self.consumption = consumption
                # List of consumption parameters for each producer
                self.param_list = []
                for priority, ratio in zip(priority_list, ratio_list):
                    self.param_list.append(Repartition.Point.ConsRepart.Param(priority, ratio))

        def __init__(self, slot):
            self.slot = slot
            self.prod_list = []
            self.cons_list = []

    def __init__(self, *prm_list):
        # List of PRM
        self.prm_list = []
        # List of points for each slot of 15 min
        self.point_list = []

    # This function adds PRM of consumers
    def add_prm(self, cons_list):
        for cons in cons_list:
            self.prm_list.append(cons.prm)

    # This function adds point with slot information
    def add_point(self, slot):
        self.point_list.append(Repartition.Point(slot))

    # This function adds production value to the point list
    def add_point_prod(self, index, prod):
        self.point_list[index].prod_list.append(Repartition.Point.ProdRepart(prod))

    # This function adds consumption value to the point list
    def add_point_cons(self, index, cons, priority, ratio):
        self.point_list[index].cons_list.append(Repartition.Point.ConsRepart(cons, priority, ratio))

    # This function returns true if at least one consumer is active
    def are_consumers_active(self, point):
        active = False
        for cons in point.cons_list:
            # if cons.active:
            if cons.state == State.ACTIVE:
                active = True
        return active

    def calculate_rep_key_dynamic_by_default(self, point):

        # First iterate on each consumer to compute global consumption
        global_consumption = 0
        for cons in point.cons_list:
            global_consumption += cons.consumption

        # Then iterate on each production to compute global production
        global_production = 0
        for prod in point.prod_list:
            global_production += prod.production

        # Compute ratio between global_consumption and global production
        # Limit value to 1 to not exceed the consumption
        ratio_conso_prod = 0
        if global_consumption > global_production:
            ratio_conso_prod = 1
        else:
            ratio_conso_prod = global_consumption / global_production

        # Iterate on each consumer to set the key and corresponding auto_consumption
        for cons in point.cons_list:
            for param, prod in zip(cons.param_list, point.prod_list):
                if global_consumption != 0:
                    param.key = cons.consumption / global_consumption
                    param.auto_consumption = prod.production * param.key * ratio_conso_prod
                else:
                    param.key = 0
                    param.auto_consumption = 0

        for cons in point.cons_list:
            for index_param, param in enumerate(cons.param_list):
                # Use floor function to round to lower value.
                # This ensures that sum of all keys does not exceed 100%
                param.key = math.floor(param.auto_consumption * 1000 / point.prod_list[index_param].initial_production) / 10

    # Function to calculate repartition keys
    def calculate_rep_key_dynamic(self, current_priority, point):

        # self.count += 1
        # print('count = ', self.count)

        # Variable to check if there is at least one consumer with current priority
        priority_exist = False

        # First iterates on all consumers to assign consumption according the ratio
        for cons in point.cons_list:

            # Check if consumer has the current priority for one of the producer
            for param in cons.param_list:
                if param.priority == current_priority:
                    priority_exist = True

            # Manage only enabled consumers and matching current priority
            if cons.state == State.ACTIVE:
                if priority_exist == True:

                    prod_total = 0
                    for param, prod in zip(cons.param_list, point.prod_list):
                        if param.priority == current_priority:
                            prod_total += (prod.production * param.key) / 100

                    # No production to use anymore with this priority => de-activate the consumer
                    if prod_total == 0:
                        cons.state = State.INACTIVE

                    # Get current auto_consumption used from all producers
                    auto_consumption_total = 0
                    for param in cons.param_list:
                            auto_consumption_total += param.auto_consumption

                    # Check if consumption from autocollect is going to exceed consumption
                    if cons.consumption < (prod_total + auto_consumption_total):
                        # If this is the case, set consumer to COMPLETE state
                        cons.state = State.COMPLETE

                        # Sum key to get new ratio
                        key_total = 0
                        for param in cons.param_list:
                            if param.priority == current_priority:
                                key_total += param.key

                        # Loop on all param to add consumption for consumer
                        for param, prod in zip(cons.param_list, point.prod_list):
                            if param.priority == current_priority:
                                # Compute the new production by first getting part of production using the key,
                                # then applying ratio using remaining consumption compared to total production.
                                new_prod = prod.production * (param.key / 100) * ((cons.consumption - auto_consumption_total) / prod_total)
                                param.auto_consumption += new_prod
                                prod.prod_to_remove += new_prod

                    else:
                        # If not, set auto_consumption according to the initial ratio
                        for param, prod in zip(cons.param_list, point.prod_list):
                            if param.priority == current_priority:
                                new_prod = (param.key * prod.production) / 100
                                prod.prod_to_remove += new_prod
                                param.auto_consumption += new_prod

                    # logger.debug("Consommation est égale à %f", cons.auto_consumption)
                    # logger.debug("Production utilisée: %f", prod_used)
                else:
                    cons.state = State.INACTIVE


        # Refresh production by removing what has been consumed by consumers
        for prod in point.prod_list:
            prod.production -= prod.prod_to_remove
            prod.prod_to_remove = 0

        # Get total production available
        prod_total = 0
        for prod in point.prod_list:
            prod_total += prod.production

        # If not all the production is used, and at least one consumer still enabled:
        # compute new ratios
        # and recursively call this function
        if ( (prod_total > 0)
            and self.are_consumers_active(point)
            and priority_exist):

            # Sum ratio of all enabled consumers
            new_sum = []
            for index_prod, prod in enumerate(point.prod_list):
                new_sum.append(0)
                for cons in point.cons_list:
                    if (cons.state == State.ACTIVE and
                        cons.param_list[index_prod].priority == current_priority):
                        new_sum[index_prod] +=  cons.param_list[index_prod].key

            # Compute new ratios
            for cons in point.cons_list:
                # Manage only enabled consumers
                if cons.state == State.ACTIVE:
                    index_param = 0
                    for param in cons.param_list:
                        if param.priority == current_priority:
                            param.key = (100 * param.key) / new_sum[index_param]
                        index_param += 1

            # Call again the function
            self.calculate_rep_key_dynamic(current_priority, point)

        # Reactivate consumer for next iteration
        if not self.are_consumers_active(point):
            for cons in point.cons_list:
                if cons.state == State.INACTIVE:
                    cons.state = State.ACTIVE

        if priority_exist:
            # increase priority
            current_priority += 1
            # Call again the function
            self.calculate_rep_key_dynamic(current_priority, point)

        # Compute final ratio for each consumer
        for cons in point.cons_list:
            for index_param, param in enumerate(cons.param_list):
                # Use floor function to round to lower value.
                # This ensures that sum of all keys does not exceed 100%
                param.key = math.floor(param.auto_consumption * 1000 / point.prod_list[index_param].initial_production) / 10

    # Function to build repartition
    def build_rep(self, prod_list, cons_list, type):

        # First get list of prm
        self.add_prm(cons_list)

        # Build for each time slot the list of points with producer and consumers values:
        #   [prod_slot1, cons1_slot1, cons2_slot1, ..., consN_slot1]
        #   [prod_slot2, cons1_slot2, cons2_slot2, ..., consN_slot2]
        #   ...
        #   [prod_slotX, cons1_slotX, cons2_slotX, ..., consN_slotX]
        # Build list of keys using initial ratio
        for i,prod_slot in enumerate(prod_list[0].point_list):
            # First add slot
            self.add_point(prod_slot.slot)

            # Populate producer list
            for producer in prod_list:
                self.add_point_prod(i, producer.point_list[i].prod)

            # Then iterate on each consumer to add its information
            for cons in cons_list:
                # In case production is 0, force consumer information to 0
                # Otherwise add consumers information and calculate repartition keys
                if producer.point_list[i].prod == 0:
                    null_ratio_list = [0 for i in range(0, len(cons.ratio_list))]
                    self.add_point_cons(i, cons.point_list[i].cons, cons.priority_list, null_ratio_list)
                else:
                    self.add_point_cons(i, cons.point_list[i].cons, cons.priority_list, cons.ratio_list)

            # Compute repartition keys only if production is not null
            if prod_slot.prod != 0:
                if type == Strategy.DYNAMIC_BY_DEFAULT:
                    self.calculate_rep_key_dynamic_by_default(self.point_list[i])
                elif type == Strategy.DYNAMIC:
                    self.calculate_rep_key_dynamic(0, self.point_list[i])
                else:
                    self.calculate_rep_key_dynamic(0, self.point_list[i])

    # This function create files for repartition keys
    def write_repartition_key(self, prod_list, cons_list, folder, debug_info = False):
        for index_prod, prod in enumerate(prod_list):
            file = folder + '/' + str(prod.prm) + '.csv'
            with open(file, 'w', newline='') as csvfile:
                keywriter = csv.writer(csvfile,delimiter=';')

                # Add first line with list of PRM
                first_line = []
                first_line.append('Horodate')
                for prm in self.prm_list:
                    first_line.append(str(prm))

                if debug_info:
                    # Start the debug information at the second line
                    line_for_debug_info = 1
                    first_line.append('TOTAL')

                    # Compute the letter of column based on number of consumers
                    # Add number of consumers + 2 columns  (Horodate and TOTAL)
                    column_letter = 'A'
                    column_letter = ord(column_letter[0]) + len(self.prm_list) + 2
                    first_line.append('=NB.SI('+chr(column_letter)+'2:'+chr(column_letter)+'2881;"NOK")')
                    line_for_debug_info += 1

                keywriter.writerow(first_line)

                # Iterate on each point
                for row in self.point_list:
                    # First add information of time slot
                    row_key = []
                    row_key.append(row.slot)
                    # Then add key for each consumer
                    for cons in row.cons_list:
                        # Use this line to print float with ',' instead of '.'
                        row_key.append(str(cons.param_list[index_prod].key).replace('.', ','))
                        # row_key.append(cons.param_list[index_prod].key)

                    if debug_info:
                        # Add check information for excel
                        line = '=SOMME('
                        excel_column_number = 'A'
                        excel_column_number = ord(excel_column_number[0])
                        for cons in cons_list:
                            excel_column_number += 1
                            line += 'SUBSTITUE('+chr(excel_column_number)+str(line_for_debug_info)+';".";",");'
                        excel_column_number +=1
                        line = line[:-1]
                        line = line + ')'
                        row_key.append(line)
                        line = '=SI('+chr(excel_column_number)+str(line_for_debug_info)+'>100;"NOK";"")'
                        row_key.append(line)
                        line_for_debug_info += 1

                    keywriter.writerow(row_key)

                print('Repartition key file written')

    # This function extract month value
    def get_month(self, slot):
        if '.' in slot:
            date_obj = datetime.strptime(slot[0:5], "%d.%m")
        elif '/' in slot:
            date_obj = datetime.strptime(slot[0:10], "%d/%m/%Y")

        month = date_obj.month
        return month

    # This function creates file with statistics (auto-consumption and auto-production)
    def generate_statistics(self,
                            prod_list,
                            cons_list,
                            folder,
                            add_cons = False,
                            add_auto_cons = True,
                            add_auto_prod_rate = False):
        file_list = []

        for index_prod, prod in enumerate(prod_list):
            file = folder + '/' + str(prod.prm) + '_statistics.csv'
            file_list.append(file)
            with open(file, 'w', newline='') as csvfile:
                keywriter = csv.writer(csvfile,delimiter=';')

                # Add first line with name of consumers
                first_line = []
                first_line.append('Horodate')
                first_line.append(prod.name)
                for cons in cons_list:
                    if add_cons: first_line.append(cons.name + "\ncons")
                    if add_auto_cons: first_line.append(cons.name + "\nauto_cons")
                    if add_auto_prod_rate: first_line.append(cons.name + "\nauto_prod_rate")
                first_line.append("auto_cons_rate")
                keywriter.writerow(first_line)

                # Iterate on each point
                for row in self.point_list:
                    # First add information of time slot
                    row_key = []
                    row_key.append(row.slot)
                    row_key.append(str(row.prod_list[index_prod].initial_production))

                    total_auto_consumption = 0

                    # Then add key for each consumer
                    for cons in row.cons_list:
                        if add_cons:
                            row_key.append(str(cons.consumption).replace('.', ','))

                        if add_auto_cons:
                            auto_cons = row.prod_list[index_prod].initial_production * cons.param_list[index_prod].key
                            auto_cons = math.floor(auto_cons) / 100
                            row_key.append(str(auto_cons).replace('.', ','))
                            # row_key.append(cons.param_list[index_prod].key)

                        if add_auto_prod_rate:
                            if (cons.consumption != 0):
                                auto_prod_rate = str(int(auto_cons * 100 / cons.consumption)).replace('.', ',')
                            else:
                                auto_prod_rate = 0
                            row_key.append(auto_prod_rate)

                        # Multiply by 100 and force to int to prevent having float representation issues
                        total_auto_consumption += int(round(cons.param_list[index_prod].auto_consumption * 100))

                    # Write auto consumption ratio
                    if row.prod_list[index_prod].initial_production != 0:
                        auto_cons_ratio = int(total_auto_consumption  / row.prod_list[index_prod].initial_production)
                    else:
                        auto_cons_ratio = 0

                    row_key.append(auto_cons_ratio)

                    keywriter.writerow(row_key)

                print('File for statistics generated')

            return file_list

    # Function used to generate monthly report
    def generate_monthly_report(self,
                                prod_list,
                                cons_list,
                                folder,
                                add_cons_mois = True,
                                add_auto_prod_rate = True,
                                add_auto_cons_mois = True):
        for index_prod, prod in enumerate(prod_list):
            file = folder + '/' + str(prod.prm) + '_monthly_report.csv'
            with open(file, 'w', newline='') as csvfile:
                keywriter = csv.writer(csvfile,delimiter=';')

                # Add first line with name of consumers
                first_line = []
                first_line.append('Horodate')
                first_line.append(prod.name + '\n prod')
                for cons in cons_list:
                    if add_cons_mois: first_line.append(cons.name + '\ncons_mois')
                    if add_auto_prod_rate: first_line.append(cons.name + '\nauto_prod_rate')
                    if add_auto_cons_mois: first_line.append(cons.name + '\nauto_cons_mois')
                keywriter.writerow(first_line)

                # Get first month
                current_month = self.get_month(self.point_list[0].slot)

                prod_month = 0
                cons_month = [0 for i in range(len(self.point_list[0].cons_list))]
                auto_cons_month = [0 for i in range(len(self.point_list[0].cons_list))]
                total_auto_consumption = 0

                # Iterate on each point
                for row_index, row in enumerate(self.point_list):

                    # Check if reaching end of file before getting next month
                    if (row_index < len(self.point_list)-1):
                        next_month = self.get_month(self.point_list[row_index+1].slot)
                    else:
                        next_month = 13

                    prod_month += row.prod_list[0].initial_production

                    # Then add key for each consumer
                    for cons_index, cons in enumerate(row.cons_list):
                        cons_month[cons_index] += cons.consumption

                        auto_cons = row.prod_list[index_prod].initial_production * cons.param_list[index_prod].key
                        auto_cons = auto_cons / 100
                        auto_cons_month[cons_index] += auto_cons
                        total_auto_consumption += auto_cons

                    # If next month is different, write the values for the current month
                    if next_month != current_month:
                        # New month => write values for current month
                        # First add information of time slot
                        row_key = []
                        row_key.append(row.slot)

                        row_key.append(str(int(prod_month/1000)).replace('.', ','))

                        for cons_index, cons in enumerate(row.cons_list):
                            cons_kwh = int(cons_month[cons_index] / 1000)
                            if add_cons_mois:
                                row_key.append(str(cons_kwh).replace('.', ','))

                            ratio = int(auto_cons_month[cons_index] * 10000 / cons_month[cons_index]) / 100
                            if add_auto_prod_rate:
                                row_key.append(str(ratio).replace('.', ','))

                            auto_cons_kwh = int(auto_cons_month[cons_index] / 1000)
                            if add_auto_cons_mois:
                                row_key.append(str(auto_cons_kwh).replace('.', ','))

                        # Reinitialize lists
                        prod_month = 0
                        cons_month = [0 for i in range(len(self.point_list[0].cons_list))]
                        auto_cons_month = [0 for i in range(len(self.point_list[0].cons_list))]

                        keywriter.writerow(row_key)

                        current_month = next_month

                print('Monthly report generated')

    # This function get auto_consumption rate for a specific producer
    # Auto_consumption rate is defined as:
    # (sum of auto_consumption for all users) / (production of producer)
    def get_auto_consumption_rate(self, index_producer):

        total_auto_consumption = 0
        total_production = 0
        for row in self.point_list:

            # First get all auto_consumption for the specific producer
            for cons in row.cons_list:
                total_auto_consumption += cons.param_list[index_producer].auto_consumption

            # Then get sum of production
            total_production += row.prod_list[index_producer].initial_production

        # Compute auto_consumption rate
        auto_consumption_rate = int(total_auto_consumption * 1000 / total_production) / 10

        return auto_consumption_rate

    # This function get auto_production rate for a specific consumer
    # Auto_production rate is defined as:
    # (sum of auto_consumption) / (sum of consumption)
    def get_auto_production_rate(self, index_consumer):

        total_auto_consumption = 0
        total_consumption = 0
        for row in self.point_list:

            for param in row.cons_list[index_consumer].param_list:
                total_auto_consumption += param.auto_consumption

            total_consumption += row.cons_list[index_consumer].consumption

        # Compute auto_production rate
        auto_production_rate = int(total_auto_consumption * 1000 / total_consumption) / 10

        return auto_production_rate

    # This function get global auto_production rate
    # Auto_production rate is defined as:
    # (sum of auto_consumption of all consumers) / (sum of consumption of all consumers)
    def get_global_auto_production_rate(self, cons_list):

        total_auto_consumption = 0
        total_consumption = 0
        for row in self.point_list:

            for cons in row.cons_list:
                for param in cons.param_list:
                    total_auto_consumption += param.auto_consumption

        for cons in cons_list:
            for point in cons.point_list:
                total_consumption += point.cons

        # Compute auto_production rate
        global_auto_production_rate = int(total_auto_consumption * 1000 / total_consumption) / 10

        return global_auto_production_rate


    # This function get coverage rate
    # Coverage rate is defined as:
    # (production of producer) / (sum of consumption of consumer)
    def get_coverage_rate(self, index_producer, cons_list):

        total_production = 0
        total_consumption = 0
        for row in self.point_list:

            total_production += row.prod_list[index_producer].initial_production

        for cons in cons_list:
            for point in cons.point_list:
                total_consumption += point.cons

        # Compute coverage rate
        coverage_rate = int(total_production * 1000 / total_consumption) / 10

        return coverage_rate