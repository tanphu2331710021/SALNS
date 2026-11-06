import math
import random
import copy
import pandas as pd

TERMINAL_TAXI_TIME = {'T1': 6 * 60, 'T2': 4 * 60, 'T3': 8 * 60}
MAX_GATE_HOLD_TIME = 600
CROSSING_TAXI_TIME = 0
NUM_RUNWAYS = 1
T_0, T_L, LAMBDA, BETA, THETA_NOTIMP = 1000.0, 1.0, 0.90, 50, 20
SEPARATION_MATRIX = {
    'S': {'S': 90,  'H': 120, 'M': 150, 'L': 180, 'A': 60},
    'H': {'S': 90,  'H': 90,  'M': 120, 'L': 150, 'A': 60},
    'M': {'S': 60,  'H': 60,  'M': 60,  'L': 90,  'A': 60},
    'L': {'S': 60,  'H': 60,  'M': 60,  'L': 60,  'A': 60},
    'A': {'S': 30,  'H': 30,  'M': 30,  'L': 30,  'A': 30}
}

def time_to_sec(val):
    if pd.isna(val) or val == "" or str(val).strip() == "" or str(val).lower() == "nan": return None
    if hasattr(val, 'strftime'):
        val = val.strftime('%H:%M:%S')
    elif hasattr(val, 'hour'):
        val = f"{val.hour:02d}:{val.minute:02d}:{val.second:02d}"
    parts = list(map(int, str(val).strip().split(':')))
    if len(parts) == 2: return parts[0] * 3600 + parts[1] * 60
    elif len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return 0

def sec_to_time(sec):
    if sec is None or sec == "": return ""
    sec = int(round(sec))
    h = sec // 3600; m = (sec % 3600) // 60; s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

class Flight:
    def __init__(self, id_code, f_type, category, terminal="", eobt_str="", etd_eta_str="", is_peak_hour=True):
        self.id_code = str(id_code).strip()
        self.type = str(f_type).strip().upper()
        self.category = str(category).strip().upper()
        self.terminal = str(terminal).strip().upper() if terminal else ""
        self.eobt_str = str(eobt_str).strip() if eobt_str else ""
        self.etd_eta_str = str(etd_eta_str).strip() if etd_eta_str else ""
        self.EOBT = time_to_sec(self.eobt_str)
        self.ETD_ETA = time_to_sec(self.etd_eta_str)
        if self.type == 'D':
            self.taxi_time = TERMINAL_TAXI_TIME.get(self.terminal, 360)
            if self.ETD_ETA is not None: self.ETD = self.ETD_ETA
            elif self.EOBT is not None: self.ETD = self.EOBT + self.taxi_time
            else: self.ETD = 0
            self.ETA = None
            self.E = self.ETD
        else:
            self.taxi_time = CROSSING_TAXI_TIME
            self.ETA = self.ETD_ETA if self.ETD_ETA is not None else 0
            self.ETD = None
            self.EOBT = None
            self.E = self.ETA + CROSSING_TAXI_TIME
        self.O_i = 2; self.R_i = 3; self.J_i = 1 if is_peak_hour else 2
        self.P_i = 1.0; self.mu = 1.0; self.t = None; self.runway = None

def setup_flight_priorities(flights, is_peak_hour=True):
    dep_ids = {f.id_code for f in flights if f.type == 'D'}
    arr_ids = {f.id_code for f in flights if f.type == 'A'}
    connecting_ids = dep_ids.intersection(arr_ids)
    R_map = {'S': 1, 'H': 2, 'M': 3, 'L': 4}
    for f in flights:
        f.O_i = 1 if f.id_code in connecting_ids else 2
        f.R_i = R_map.get(f.category, 3)
        f.J_i = 1 if is_peak_hour else 2
        PF = f.O_i + f.R_i + f.J_i
        term1 = (PF - 1) * (PF - 2) * (PF - 3) / 6.0
        term2 = (2 * PF - f.O_i - 2) * (f.O_i - 1) / 2.0
        f.P_i = term1 + term2 + f.J_i
        f.mu = 48.0 / f.P_i

def check_queue_limit(candidate_t, flight, scheduled_flights):
    arrivals = [f for f in scheduled_flights if f.type == 'A']
    if flight.type == 'A':
        temp_f = copy.copy(flight); temp_f.t = candidate_t; arrivals.append(temp_f)
    events = []
    for a in arrivals:
        events.append((a.E, 1)); events.append((a.t, -1))
    events.sort(key=lambda x: (x[0], x[1]))
    q_size = 0
    for t_ev, diff in events:
        q_size += diff
        if q_size > 2: return False
    return True

def is_valid_insertion(runway_flights, flight, candidate_t):
    if candidate_t < flight.E: return False
    for other in runway_flights:
        if candidate_t == other.t: return False
        if flight.type == 'D' and other.type == 'A':
            sep_after_landing = SEPARATION_MATRIX[other.category][flight.category]
            if other.ETA - 120 <= candidate_t < other.ETA + sep_after_landing: return False
        elif flight.type == 'A' and other.type == 'D':
            sep_after_landing = SEPARATION_MATRIX[flight.category][other.category]
            if flight.ETA - 120 <= other.t < flight.ETA + sep_after_landing: return False
        cat_other = other.category if other.type == 'D' else 'A'
        cat_flight = flight.category if flight.type == 'D' else 'A'
        if other.t < candidate_t:
            req_sep = SEPARATION_MATRIX[cat_other][cat_flight]
            if candidate_t - other.t < req_sep: return False
        else:
            req_sep = SEPARATION_MATRIX[cat_flight][cat_other]
            if other.t - candidate_t < req_sep: return False
    if not check_queue_limit(candidate_t, flight, runway_flights): return False
    return True

def get_candidate_times(runway_flights, flight):
    candidates = set([flight.E])
    cat_flight = flight.category if flight.type == 'D' else 'A'
    for other in runway_flights:
        cat_other = other.category if other.type == 'D' else 'A'
        earliest_after_other = other.t + SEPARATION_MATRIX[cat_other][cat_flight]
        candidates.add(earliest_after_other)
        if other.type == 'A' and flight.type == 'D':
            sep_landing = SEPARATION_MATRIX[other.category][flight.category]
            candidates.add(other.ETA + sep_landing)
    valid_candidates = []
    for ct in sorted(list(candidates)):
        if ct >= flight.E and is_valid_insertion(runway_flights, flight, ct):
            valid_candidates.append(ct)
    return valid_candidates

def eval_obj1(flights):
    total_cost = 0.0
    for f in flights:
        if f.t is None: return float('inf')
        if f.type == 'D': total_cost += f.mu * (f.t - f.ETD)
        else: total_cost += 1.0 * f.mu * max(0, f.t - f.E)
    return total_cost

def eval_obj2(flights):
    total_cost = 0.0
    for f in flights:
        if f.t is None: return float('inf')
        if f.type == 'D': total_cost += f.mu * (f.t - f.ETD)
        else: total_cost += 1000.0 * f.mu * max(0, f.t - f.E)
    return total_cost

def get_best_insertion(runways, flight, eval_func):
    best_cost_diff = float('inf')
    best_r = -1; best_idx = -1; best_t = -1
    for r in range(NUM_RUNWAYS):
        rw_flights = runways[r]
        valid_times = get_candidate_times(rw_flights, flight)
        for candidate_t in valid_times:
            idx = 0
            while idx < len(rw_flights) and rw_flights[idx].t < candidate_t: idx += 1
            if eval_func == eval_obj1:
                cost = (flight.mu * (candidate_t - flight.ETD)) if flight.type == 'D' else (1.0 * flight.mu * max(0, candidate_t - flight.E))
            else:
                cost = (flight.mu * (candidate_t - flight.ETD)) if flight.type == 'D' else (1000.0 * flight.mu * max(0, candidate_t - flight.E))
            if cost < best_cost_diff:
                best_cost_diff = cost; best_r = r; best_idx = idx; best_t = candidate_t
    return best_r, best_idx, best_t

def greedy_schedule(flight_list, eval_func):
    sorted_flights = sorted(flight_list, key=lambda f: f.E)
    runways = [[] for _ in range(NUM_RUNWAYS)]
    for f in sorted_flights:
        f_copy = copy.deepcopy(f)
        best_r, best_idx, best_t = get_best_insertion(runways, f_copy, eval_func)
        if best_r != -1:
            f_copy.t = best_t; f_copy.runway = best_r
            runways[best_r].insert(best_idx, f_copy)
        else:
            max_t = f_copy.E
            for r in range(NUM_RUNWAYS):
                if runways[r]: max_t = max(max_t, runways[r][-1].t + 120)
            f_copy.t = max_t; f_copy.runway = 0
            runways[0].append(f_copy)
    scheduled = []
    for r in range(NUM_RUNWAYS): scheduled.extend(runways[r])
    return scheduled, eval_func(scheduled)

def salns_optimize(flight_list, eval_func, num_runs=10):
    best_overall_sol = None
    best_overall_cost = float('inf')
    for run in range(num_runs):
        initial_sol, initial_cost = greedy_schedule(flight_list, eval_func)
        current_solution = copy.deepcopy(initial_sol)
        current_cost = initial_cost
        best_run_sol = copy.deepcopy(current_solution)
        best_run_cost = current_cost
        T = T_0; mu = 0
        while T > T_L and mu < THETA_NOTIMP:
            improved_in_temp = False
            for _ in range(BETA):
                num_to_remove = max(1, int(len(current_solution) * random.uniform(0.1, 0.3)))
                remove_indices = random.sample(range(len(current_solution)), num_to_remove)
                removed_flights = [current_solution[i] for i in remove_indices]
                remaining_flights = [current_solution[i] for i in range(len(current_solution)) if i not in remove_indices]
                temp_runways = [[] for _ in range(NUM_RUNWAYS)]
                for f in remaining_flights: temp_runways[f.runway].append(f)
                for r in range(NUM_RUNWAYS): temp_runways[r].sort(key=lambda x: x.t)
                random.shuffle(removed_flights)
                valid_repair = True
                for rf in removed_flights:
                    rf_clean = copy.deepcopy(rf)
                    rf_clean.t = None; rf_clean.runway = None
                    best_r, best_idx, best_t = get_best_insertion(temp_runways, rf_clean, eval_func)
                    if best_r != -1:
                        rf_clean.t = best_t; rf_clean.runway = best_r
                        temp_runways[best_r].insert(best_idx, rf_clean)
                    else:
                        valid_repair = False; break
                if valid_repair:
                    neighbor = []
                    for r in range(NUM_RUNWAYS): neighbor.extend(temp_runways[r])
                    neighbor_cost = eval_func(neighbor)
                    if neighbor_cost < current_cost:
                        current_solution = neighbor; current_cost = neighbor_cost
                        if neighbor_cost < best_run_cost:
                            best_run_sol = copy.deepcopy(neighbor); best_run_cost = neighbor_cost; improved_in_temp = True
                    else:
                        try: prob = math.exp(-(neighbor_cost - current_cost) / T)
                        except OverflowError: prob = 0
                        if random.random() < prob:
                            current_solution = neighbor; current_cost = neighbor_cost
            T *= LAMBDA
            if not improved_in_temp: mu += 1
            else: mu = 0
        if best_run_cost < best_overall_cost:
            best_overall_cost = best_run_cost
            best_overall_sol = copy.deepcopy(best_run_sol)
    return best_overall_sol, best_overall_cost

def process_output(sol, is_option_2=False):
    sol_sorted = sorted(sol, key=lambda x: x.t)
    out_data = []
    for i, f in enumerate(sol_sorted):
        if f.type == 'D':
            delay = f.t - f.ETD
            latest_pushback = f.t - f.taxi_time
            aobt_sec = max(f.EOBT, min(f.EOBT + MAX_GATE_HOLD_TIME, latest_pushback))
            gate_wait = aobt_sec - f.EOBT
            holding_wait = f.t - (aobt_sec + f.taxi_time)
            flight_cost = f.mu * delay
            out_data.append({
                "STT": i + 1, "Mã chuyến bay": f.id_code, "Loại": f.type, "Hạng": f.category,
                "Nhà ga": f.terminal, "EOBT": sec_to_time(f.EOBT), "AOBT": sec_to_time(aobt_sec),
                "ETD/ETA": sec_to_time(f.ETD), "ATD/ATA": sec_to_time(f.t),
                "Chờ tại Gate": sec_to_time(gate_wait), "Chờ tại Holding": sec_to_time(holding_wait),
                "Thời gian Delay": sec_to_time(delay), "Hệ số P": round(f.P_i, 2),
                "Hệ số μ": round(f.mu, 3), "Chi phí trễ": round(flight_cost, 2)
            })
        else:
            holding_wait = max(0, f.t - f.E)
            delay = holding_wait
            flight_cost = (1000.0 if is_option_2 else 1.0) * f.mu * delay
            out_data.append({
                "STT": i + 1, "Mã chuyến bay": f.id_code, "Loại": f.type, "Hạng": f.category,
                "Nhà ga": "", "EOBT": "", "AOBT": "",
                "ETD/ETA": sec_to_time(f.ETA), "ATD/ATA": sec_to_time(f.t),
                "Chờ tại Gate": "", "Chờ tại Holding": sec_to_time(holding_wait),
                "Thời gian Delay": sec_to_time(delay), "Hệ số P": round(f.P_i, 2),
                "Hệ số μ": round(f.mu, 3), "Chi phí trễ": round(flight_cost, 2)
            })
    return pd.DataFrame(out_data)

def run_optimization(df, is_peak_hour=True, num_runs=10):
    flights = []
    for _, row in df.iterrows():
        id_code = str(row.get('CALL SIGN', row.get('Mã chuyến bay', '')))
        f_type = str(row.get('TYPE A/C', row.get('Loại', '')))
        cat = str(row.get('WAKE TURBULENCE', row.get('Hạng', 'M')))
        terminal = str(row.get('TERMINAL', row.get('Nhà ga', ''))) if f_type.upper() == 'D' else ""
        eobt = str(row.get('EOBT', '')) if f_type.upper() == 'D' else ""
        etd_eta = str(row.get('ETD/ETA', ''))
        if id_code and f_type:
            flights.append(Flight(id_code, f_type, cat, terminal, eobt, etd_eta, is_peak_hour))
            
    setup_flight_priorities(flights, is_peak_hour)

    g1, _ = greedy_schedule(flights, eval_obj1)
    s1, _ = salns_optimize(flights, eval_obj1, num_runs)
    g2, _ = greedy_schedule(flights, eval_obj2)
    s2, _ = salns_optimize(flights, eval_obj2, num_runs)

    return {
        "PA1_Greedy_Baseline": process_output(g1, False),
        "PA1_SALNS_Toi_Uu": process_output(s1, False),
        "PA2_Greedy_Baseline": process_output(g2, True),
        "PA2_SALNS_Toi_Uu": process_output(s2, True)
    }
