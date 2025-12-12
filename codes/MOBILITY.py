import numpy as np
import random
import math

def levy_random_walk(alpha, beta, n_steps):
 
    step_lengths = (1 - np.random.uniform(0, 1, n_steps))**(-1/alpha)
    pause_times = (1 - np.random.uniform(0, 1, n_steps))**(-1/beta)

    steps = []
    current_pos = np.array([0.0, 0.0])
    for i in range(n_steps):
        # Truncation: limit step length to a maximum value
        step_len = min(step_lengths[i], 100) # example truncation at 100 units
        
        angle = random.uniform(0, 2 * math.pi)
        move_vector = np.array([step_len * math.cos(angle), step_len * math.sin(angle)])
        
        current_pos += move_vector
        steps.append(current_pos.copy())
    
    return np.array(steps)

def gauss_markov_model(n_steps, v_avg, a_factor):
 
    velocities = np.zeros((n_steps, 2))
    positions = np.zeros((n_steps, 2))
    
    for i in range(1, n_steps):
        # Generate new velocity based on previous state
        noise = np.random.normal(0, a_factor, 2)
        velocities[i] = a_factor * velocities[i-1] + noise
        
        positions[i] = positions[i-1] + velocities[i]
        
    return positions

def combined_mobility_scenario(num_nodes, duration_sec, time_step, levy_prob, levy_params, gauss_params):
    """
    Creates a combined mobility scenario.
    Outputs positions to a positions.dat file for Cooja.
    """
    n_steps = int(duration_sec / time_step)
    all_positions = []
    
    for node_id in range(num_nodes):
        node_positions = []
        current_pos = np.array([0.0, 0.0])
        current_vel = np.array([0.0, 0.0])
        
        for step in range(n_steps):
            if random.random() < levy_prob:
                # Use Truncated Levy Walk
                step_len = (1 - random.uniform(0, 1))**(-1/levy_params['alpha'])
                step_len = min(step_len, levy_params['truncation']) # Truncation
                
                angle = random.uniform(0, 2 * math.pi)
                move_vector = np.array([step_len * math.cos(angle), step_len * math.sin(angle)])
                
                current_pos += move_vector
                
            else:
                # Use Gauss-Markov
                noise = np.random.normal(0, gauss_params['a_factor'], 2)
                current_vel = gauss_params['a_factor'] * current_vel + noise
                
                current_pos += current_vel
                
            node_positions.append([step * time_step, node_id, current_pos[0], current_pos[1], 0.0])
            
        all_positions.extend(node_positions)

    # Write to positions.dat file
    with open('positions.dat', 'w') as f:
        f.write("# Cooja positions.dat file\n")
        f.write("# Format: time(s) id x y z\n")
        for pos in all_positions:
            f.write(f"{pos[0]:.2f}\t{pos[1]}\t{pos[2]:.2f}\t{pos[3]:.2f}\t{pos[4]:.2f}\n")
            
    print("positions.dat file created successfully!")



if __name__ == "__main__":
    
    num_nodes = 50
    duration_sec = 3600
    time_step = 1.0
    levy_prob = 0.5  # 50% chance of using Lévy Walk
    
    # Parameters for Truncated Levy Walk
    levy_params = {
        'alpha': 1.5,
        'beta': 0.5,
        'truncation': 20.0 # Max step length
    }
    
    # Parameters for Gaussian-Markov
    gauss_params = {
        'v_avg': 1.0,
        'a_factor': 0.5
    }
    
    combined_mobility_scenario(num_nodes, duration_sec, time_step, levy_prob, levy_params, gauss_params)