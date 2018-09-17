
import time
import traceback
import os
from qutip import basis, ket, mesolve, qeye, tensor, thermal_dm, destroy, steadystate, Qobj, enr_thermal_dm
import qutip as qt
import matplotlib.pyplot as plt
import numpy as np
from numpy import pi
import phonons as RC
import optical as EM

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

def bias_dependence_function(eps, **kwargs):
    args = kwargs['kwargs']
    args.update({'bias': eps})
    args.update({'w_1': args['w_2']+eps})
    args.update({'w_xx': args['w_1'] + args['w_2']})
    args.update({'mu': args['w_2']/(args['w_1']) })
    args.update({'num_cpus':1})
    I = args['I']
    energies, states = exciton_states(args)
    coh =  tensor(states[0]*states[1].dag(), I)
    bright =  tensor(states[1]*states[1].dag(), I)
    dark =  tensor(states[0]*states[0].dag(), I)

    L_RC, H, A_1, A_2, SIGMA_1, SIGMA_2, args = RC.RC_mapping_OD(args)
    A_EM = SIGMA_1 + args['mu']*SIGMA_2
    assert (args['alpha_1'] != 0) and (args['alpha_2'] != 0) # temporary bug workaround
    method = 'iterative-lgmres'
    ss_p, ss_s, ss_ns = None, None, None
    try:
        L_nrwa = EM.L_non_rwa(H, A_EM, args)
        ti = time.time()
        ss_nrwa = steadystate(H, [L_RC+L_nrwa], method=method, use_precond=True)
        print "Calculating the non-rotating-wave steady state took {} seconds".format(time.time()-ti)
        del L_nrwa

        L_s = EM.L_secular(H, A_EM, args)
        ti = time.time()
        ss_s = steadystate(H, [L_RC+L_s], method=method, use_precond=True)
        print "Calculating the sec steady state took {} seconds".format(time.time()-ti)
        del L_s

        L_ns = EM.L_nonsecular(H, A_EM, args)
        ti = time.time()
        ss_ns = steadystate(H, [L_RC+L_ns], method=method, use_precond=True)
        print "Calculating the nonsec steady state took {} seconds".format(time.time()-ti)
        del L_ns

        L_p = EM.L_phenom(I, args)
        ti = time.time()
        ss_p = steadystate(H, [L_RC+L_p], method=method, use_precond=True)
        print "Calculating the phen steady state took {} seconds".format(time.time()-ti)
        del L_p

    except Exception as Err:
        var = traceback.format_exc()
        print var
        print "Could not build preconditioner, solving steadystate without one"
    print "Redfield: coh={}, dark={}, bright={}".format((ss_ns*coh).tr(), (ss_ns*dark).tr(), (ss_ns*bright).tr())
    return ss_p, ss_s, ss_ns, ss_nrwa, coh, bright, dark


def bias_dependence(biases, args, I):
    enc_dir = 'DATA/'
    print int(args['w0_1']), args['N_1'], int(args['V']), int(args['wc'])
    main_dir = enc_dir+'bias_dependence_wRC{}_N{}_V{}_wc{}/'.format(int(args['w0_1']), args['N_1'], int(args['V']), int(args['wc']))
    ops_dir = main_dir+'operators/'
    test_file = main_dir+'nonsecular/steadystate_DMs_alpha{}.pickle'.format(int(args['alpha_1']))
    coh_ops = []
    bright_ops = []
    dark_ops = []
    args.update({'I': I})
    if not os.path.isfile(test_file):
        ss_p, ss_s, ss_ns, ss_nrwa, coh_ops, bright_ops, dark_ops = qt.parfor(
                        bias_dependence_function, biases, kwargs=args)

        if not os.path.exists(ops_dir):
            '''If the data directory doesn't exist:
            make it, put operators subdir, save inital ss data in dir and ops in subdir once.
            If it exists, just save the ss data to the directory'''
            os.makedirs(main_dir)
            os.makedirs(ops_dir)
            os.makedirs(main_dir+'nonRWA')
            os.makedirs(main_dir+'nonsecular')
            os.makedirs(main_dir+'secular')
            os.makedirs(main_dir+'phenom')
        save_obj(ss_p, main_dir+'phenom/steadystate_DMs_alpha{}'.format(int(args['alpha_1'])))
        save_obj(ss_s, main_dir+'secular/steadystate_DMs_alpha{}'.format(int(args['alpha_1'])))
        save_obj(ss_ns, main_dir+'nonsecular/steadystate_DMs_alpha{}'.format(int(args['alpha_1'])))
        save_obj(ss_nrwa, main_dir+'nonRWA/steadystate_DMs_alpha{}'.format(int(args['alpha_1'])))
        save_obj(coh_ops, ops_dir+'eigcoherence_ops')
        save_obj(dark_ops, ops_dir+'dark_ops')
        save_obj(bright_ops, ops_dir+'bright_ops')
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