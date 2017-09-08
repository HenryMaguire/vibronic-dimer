
import time
import os
from qutip import basis, ket, mesolve, qeye, tensor, thermal_dm, destroy, steadystate, Qobj, enr_thermal_dm
import qutip as qt
import matplotlib.pyplot as plt
import numpy as np
from numpy import pi
import dimer_phonons as RC
import dimer_optical as EM

#import electronic_lindblad as EM_naive
from utils import *
reload(RC)
reload(EM)

def steadystate_comparison(H, L, O):
    """ Compares all the steadystate solvers and compares trace to direct method
    It seems iterative-lgmres with a preconditioner is much faster than the full factorisation methods
    """
    t0 = time.time()
    ss_dir = steadystate(H, L, method='direct')
    t1 = time.time()
    print "direct method took ", t1-t0, ' seconds'
    print "State population is: ", (O*ss_dir).tr()
    print "eigs are: ", ss_dir.eigenenergies()

    #ss_eigen = steadystate(H, L, method='eigen')
    t2 = time.time()
    #print "eigen method took ", t2-t1, "seconds and is ", ((ss_dir-ss_eigen)*(ss_dir-ss_eigen)).tr(), " away"
    #del(ss_eigen)

    ss_power = steadystate(H, L, method='power')
    t3 = time.time()
    print "power method took ", t3-t2, "seconds and is ", ss_dir.dims, ss_power.dims, " away"
    print "State population is: ", (O*ss_power).tr()
    print "eigs are: ", ss_power.eigenenergies()
    del(ss_power)

    #ss_iter = steadystate(H, L, method= 'iterative-gmres')
    t4 = time.time()
    #print "iterative-gmres method took ", t4-t3, "seconds and is ", (ss_dir-ss_iter).tr(), " away"
    #del(ss_iter)
    ss_iter = steadystate(H, L, method= 'iterative-gmres', use_precond=True)
    t5 = time.time()
    print "iterative-gmres method with preconditioner took ", t5-t4, "seconds and is ", (ss_dir-ss_iter).tr(), " away"
    print "State population is: ", (O*ss_iter).tr()
    print "eigs are: ", ss_iter.eigenenergies()
    ss_iter = steadystate(H, L, method= 'iterative-lgmres', use_precond=True)
    t6 = time.time()
    print "iterative-lgmres method with preconditioner took ", t6-t5, "seconds and is ", (ss_dir-ss_iter).tr(), " away"
    print "State population is: ", (O*ss_iter).tr()
    ss_iter = steadystate(H, L, method= 'iterative-bicgstab', use_precond=True)
    t7 = time.time()
    print "iterative-bicgstab method with preconditioner took ", t7-t6, "seconds and is ", (ss_dir-ss_iter).tr(), " away"
    print "State population is: ", (O*ss_iter).tr()

def get_coh_ops(args, biases, I):
    """ Just calculates all of the exciton coherence observable operators
    For bias dependence plots
    """
    coh_ops = []
    for eps in biases:
        args.update({'w_2': args['w_1']-eps})
        args.update({'w_xx': args['w_1'] + args['w_2'] + args['V']})
        args.update({'w_opt': (args['w_1']+args['w_2'])*0.5})
        energies, states = exciton_states(args)
        coh =  states[0]*states[1].dag()
        coh = tensor(coh, I)
        coh_ops.append(coh)
    save_obj(coh_ops, 'DATA/zoomed_coherence_ops_N{}_wRC{}'.format(args['N_1'], int(args['w0_1'])))
def exciton_states(PARS):
    w_1, w_2, V, eps = PARS['w_1'], PARS['w_2'],PARS['V'], PARS['bias']
    eta = np.sqrt(eps**2 + 4*V**2)
    lam_m = ((w_2+eps)+w_2-eta)*0.5
    lam_p = ((w_2+eps)+w_2+eta)*0.5
    v_p = qt.Qobj(np.array([0., np.sqrt(eta+eps), np.sqrt(eta-eps), 0.]))/np.sqrt(2*eta)
    v_m = qt.Qobj(np.array([0., np.sqrt(eta-eps), -np.sqrt(eta+eps), 0.]))/np.sqrt(2*eta)

    return [lam_m, lam_p], [v_m, v_p]

def exciton_states_old(PARS):
    w_1, w_2, V, bias = PARS['w_1'], PARS['w_2'],PARS['V'], PARS['bias']
    v_p, v_m = 0, 0
    eta = np.sqrt(4*(V**2)+bias**2)
    lam_p = w_2+(bias+eta)*0.5
    lam_m = w_2+(bias-eta)*0.5
    v_m = np.array([0., -(w_1-lam_p)/V, -1, 0.])
    #v_p/= /(1+(V/(w_2-lam_m))**2)
    v_m/= np.sqrt(np.dot(v_m, v_m))
    v_p = np.array([0, V/(w_2-lam_m),1., 0.])

    v_p /= np.sqrt(np.dot(v_p, v_p))
    #print  np.dot(v_p, v_m) < 1E-15
    return [lam_m, lam_p], [qt.Qobj(v_m), qt.Qobj(v_p)]

def get_dimer_info(rho, ops):
    g = (rho*ops[0]).tr()
    e1 = (rho*ops[1]).tr()
    e2 = (rho*ops[2]).tr()
    xx = (rho*ops[3]).tr()
    e1e2 = (rho*ops[4]).tr()
    e2e1 = (rho*ops[4]).dag().tr()
    return Qobj([[g.real, 0,0,0], [0, e1.real,e1e2,0],[0, e2e1,e2.real,0],[0, 0,0,xx.real]])#/(g+e1+e2+xx)

def ss_from_dynamics(DATA):
    g = DATA.expect[0][-1]
    e1 = DATA.expect[1][-1]
    e2 = DATA.expect[2][-1]
    xx = DATA.expect[3][-1]
    e1e2 = DATA.expect[4][-1]
    e2e1 = DATA.expect[4][-1].conjugate()
    return Qobj([[g.real, 0,0,0], [0, e1.real,e1e2.real,0],[0, e2e1.real,e2.real,0],[0, 0,0,xx.real]])

def bias_dependence_function(eps, args={}):
    args.update({'bias': eps})
    args.update({'w_1': args['w_2']+eps})
    args.update({'w_xx': args['w_1'] + args['w_2'] + args['V']})
    args.update({'mu': args['w_2']/(args['w_1']) })
    args.update({'num_cpus':1})
    I = args['I']
    energies, states = exciton_states(args)
    coh =  tensor(states[0]*states[1].dag(), I)
    bright =  tensor(states[1]*states[1].dag(), I)
    dark =  tensor(states[0]*states[0].dag(), I)

    L_RC, H, A_1, A_2, A_EM, wRC_1, wRC_2, kappa_1, kappa_2 = RC.RC_mapping_UD(args)
    L_ns = 0
    L_ns = EM.L_nonsecular(H, A_EM, args)

    #L_p = EM.L_phenom(states, energies, I, args)

    ti = time.time()

    method = 'iterative-lgmres'
    try:
        ss_ns = steadystate(H, [L_RC+L_ns], method=method, use_precond=True)
        #ss_p = steadystate(H, [p*L_RC+L_p], method=method, use_precond=True)
    except:
        print "Could not build preconditioner, solving steadystate without one"
        ss_ns = steadystate(H, [L_RC+L_ns], method= method)
        #ss_p = steadystate(H, [p*L_RC+L_p], method=method)
    if (args['alpha_1'] == 0) and (args['alpha_2'] == 0) and  (args['bias'] == 0):
        n_RC_1 = Occupation(args['w0_1'], args['T_1'])
        n_RC_2 = Occupation(args['w0_2'], args['T_2'])
        #rho_T = Qobj((-1/(args['T_1']*0.695))*H).expm()
        thermal_RCs = enr_thermal_dm([args['N_1'],args['N_2']], args['exc'], [n_RC_1, n_RC_2])
        #rho_0 = rho_T/rho_T.tr()

        rho_0 = tensor(basis(4,0)*basis(4,0).dag(),thermal_RCs)
        timelist = np.linspace(0,4,4000)
        opts = qt.Options(store_final_state=True)
        DATA_ns = mesolve(H, rho_0, timelist, [L_RC+L_ns], ops+[dark, bright, coh], options=opts, progress_bar=True)

        ss_ns = DATA_ns.final_state
        #DATA_p = mesolve(H, rho_0, timelist, [p*L_RC+L_p], ops+[dark, bright, coh], options=opts, progress_bar=True)
    else:
        pass

    ns_b = ss_ns.diag() <0
    #p_b = ss_p.diag() <0
    if True in ns_b:
        print "There were negative populations in non-secular dynamics for bias={}.".format(eps)
    #if True in p_b:
    #    print "There were negative populations in phenom."

    #ss_p_list.append(ss_p)
    print "Redfield: coh={}, dark={}, bright={}".format((ss_ns*coh).tr(), (ss_ns*dark).tr(), (ss_ns*bright).tr())
    print "Calculating the steady state took {} seconds".format(time.time()-ti)
    return ss_ns, coh, bright, dark


def bias_dependence(biases, args, ops):
    enc_dir = 'DATA/'
    main_dir = enc_dir+'bias_dependence_wRC{}_N{}_V{}_wc{}/'.format(int(args['w0_1']), args['N_1'], int(args['V']), int(args['wc']))
    ops_dir = main_dir+'operators/'
    test_file = main_dir+'nonsecular/steadystate_DMs_pialpha{}.pickle'.format(int(pi*args['alpha_1']))
    coh_ops = []
    bright_ops = []
    dark_ops = []
    args.update({'I': qt.enr_identity([args['N_1'],args['N_2']], args['exc'])})

    if not os.path.isfile(test_file):
        ss_ns_list, coh_ops, bright_ops, dark_ops = qt.parfor(bias_dependence_function, biases, num_cpus =args['num_cpus'], args=args)
        # = O

        if not os.path.exists(ops_dir):
            '''If the data directory doesn't exist:
            make it, put operators subdir, save inital ss data in dir and ops in subdir once.
            If it exists, just save the ss data to the directory'''
            os.makedirs(main_dir)
            os.makedirs(ops_dir)
            os.makedirs(main_dir+'nonsecular')
            #os.makedirs(main_dir+'phenom')
            #save_obj(ss_p_list, main_dir+'phenom/steadystate_DMs_alpha{}'.format(int(args['alpha_1'])))
            save_obj(ss_ns_list, main_dir+'nonsecular/steadystate_DMs_pialpha{}'.format(int(pi*args['alpha_1'])))
            save_obj(coh_ops, ops_dir+'eigcoherence_ops')
            save_obj(dark_ops, ops_dir+'dark_ops')
            save_obj(bright_ops, ops_dir+'bright_ops')
        else:
            #save_obj(ss_p_list, main_dir+'phenom/steadystate_DMs_alpha{}'.format(int(args['alpha_1'])))
            save_obj(ss_ns_list, main_dir+'nonsecular/steadystate_DMs_pialpha{}'.format(int(pi*args['alpha_1'])))
            pass
        #print "file saving at {}".format(main_dir+'steadystate_DMs_pialpha{}'.format(int(pi*args['alpha_1'])))
        #print "Data found for pi*alpha = {}".format(int(args['alpha_1'])*pi)
    else:

        print "Data already exists at {}. Skipping...".format(main_dir+'nonsecular/steadystate_DMs_pialpha{}'.format(int(pi*args['alpha_1'])))

    return

def SS_convergence_check(sigma, w_1, w_2, w_xx, V, T_1, T_2, w0_1, w0_2, alpha_1, alpha_2, wc,  alpha_EM, T_EM, mu=0, expect_op='bright', time_units='cm', start_n=2, end_n=5, method='direct'):

    """
    TODO: rewrite this entire method to take in the dimer parameters
          Plot all of the state populations
    """
    # Only for Hamiltonians of rotating wave form
    XO = basis(4,1)
    OX = basis(4,2)
    ss_list_s,ss_list_ns,ss_list_naive  = [],[],[] # steady states
    r_vector = XO+OX # r_vector is the ket vector on the right in the .matrix_element operation. Default is E.
    l_vector = (XO+OX).dag() # Default is bright state
    N_values = range(start_n,end_n)
    eps = w_1-w_2
    if expect_op == 'coherence':
        l_vector = (G-E).dag()
    else:
        pass
    for n in N_values:
        L_RC, H, A_1, A_2, A_EM, wRC_1, wRC_2 = RC.RC_mapping_UD(w_1, w_2, w_xx, V, T_1, T_2, w0_1, w0_2, alpha_1, alpha_2, wc,  n, N_2=n, mu=mu, time_units='cm')
        #L_s = EM.L_vib_lindblad(H, A_EM, alpha_EM, T_EM)
        L_ns = EM.L_nonsecular(H, A_EM, alpha_EM, T_EM)
        L_naive = EM_naive.electronic_lindblad(w_xx, w_1, eps, V, mu, alpha_EM, T_EM, n, n, 2*n)
        #ss_s = steadystate(H, [L_RC+L_s], method=method).ptrace(0)
        ss_ns = steadystate(H, [L_RC+L_ns], method=method).ptrace(0)
        ss_naive = steadystate(H, [L_RC+L_naive], method=method).ptrace(0)
        #ss_list_s.append(ss_s.matrix_element(l_vector, r_vector))
        ss_list_ns.append(ss_ns.matrix_element(l_vector, r_vector))
        ss_list_naive.append(ss_naive.matrix_element(l_vector, r_vector))
        print "N=", n, "\n -----------------------------"
    plt.figure()
    #plt.ylim(0,0.4)
    #plt.plot(N_values, ss_list_s, label='secular')
    plt.plot(N_values, ss_list_ns, label='non-secular')
    plt.plot(N_values, ss_list_naive, label='naive')
    plt.legend()
    plt.ylabel("Excited state population")
    plt.xlabel("RC Hilbert space dimension")
    p_file_name = "Notes/Images/Checks/SuperPop_convergence_a{:d}_Tem{:d}_w0{:d}_eps{:d}_{}.pdf".format(int(alpha_1), int(T_EM), int(w0_1), int(eps), method)
    plt.savefig(p_file_name)
    return ss_list_s,ss_list_ns,ss_list_naive, p_file_name
"""
if __name__ == "__main__":
    OO = basis(4,0)
    XO = basis(4,1)
    OX = basis(4,2)
    XX = basis(4,3)
    sigma_m1 = OX*XX.dag() + OO*XO.dag()
    sigma_m2 = XO*XX.dag() + OO*OX.dag()
    sigma_x1 = sigma_m1+sigma_m1.dag()
    sigma_x2 = sigma_m2+sigma_m2.dag()

    w_1 = 6000
    w_2 = 5000
    V = 1000
    eps = w_1-w_2

    T_EM = 6000. # Optical bath temperature
    alpha_EM = 0.3 # System-bath strength (optical)
    mu = 0

    T_2 = T_1 = 300. # Phonon bath temperature

    wc = 53. # Ind.-Boson frame phonon cutoff freq
    w0_2  = w0_1 = 300. # underdamped SD parameter omega_0
    w_xx = w0_2 + w0_1 + V
    alpha_2 = alpha_1 = 400. # Ind.-Boson frame coupling
    #N_1 = 6 # set Hilbert space sizes
    #N_2 = 6
    #Now we build all the operators

    L_RC, H, A_EM, A_nrwa, wRC, kappa= RC.RC_function_UD(sigma, eps, T_ph, wc, w0, alpha_ph, N)
    L_s = EM.L_vib_lindblad(H, A_EM, alpha_EM, T_EM)
    L_ns = EM.L_nonsecular(H, A_EM, alpha_EM, T_EM)
    L_naive = EM.L_EM_lindblad(eps, A_EM, alpha_EM, T_EM)
    ss_naive = steadystate(H, [L_RC+L_naive]).ptrace(0)
    #TD, rates  = nonsec_check_A(H, A_EM, alpha_EM, T_EM, N)
    #plt.figure()
    #plt.scatter(TD, rates)
    #plt.show()

    plt.figure()
    ss_list_s,ss_list_ns,ss_list_naive, p_file_name = SS_convergence_check(sigma_m1+(1-mu)*sigma_m1, w_1, w_2, w_xx, V, T_1, T_2, w0_1, w0_2, alpha_1, alpha_2, wc,  alpha_EM, T_EM, start_n = 2, end_n=5)
    #eps_values = range(1000, 2000, 50)+range(2000, 4000, 500)+range(4000, 14000, 1000)
    #N_values = [30]*len(range(1000, 2000, 50)) + [20]*len(range(2000, 4000, 500)) + [12]*len(range(4000, 14000, 1000))
    #solver_method = 'power'
    #ss_list_s,ss_list_ns,ss_list_naive, p_file_name = plot_SS_divergences(sigma, eps, T_EM, T_ph, wc, w0, alpha_ph, alpha_EM, N_values, eps_values, method=solver_method)
    print "Plot saved: ",p_file_name
    plt.savefig(p_file_name)
    plt.close()"""