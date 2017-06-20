import sys
from numpy import pi
import numpy as np

from qutip import Qobj, basis, ket, mesolve, qeye, tensor, thermal_dm, destroy, enr_identity, enr_destroy, enr_thermal_dm
import qutip as qt
import matplotlib.pyplot as plt
import matplotlib
from matplotlib import gridspec

import dimer_phonons as RC
import dimer_optical as EM
from utils import *
import dimer_plotting as vis
import dimer_checking as check
matplotlib.style.use('ggplot')
reload(RC)
reload(EM)
reload(vis)
reload(check)



def get_dimer_info(rho):
    e1e2 = tensor(basis(4,1)*basis(4,2).dag(), I)
    e2e1 = tensor(basis(4,2)*basis(4,1).dag(), I)
    g = (rho*OO).tr()
    e1 = (rho*XO).tr()
    e2 = (rho*OX).tr()

    e1e2 = (rho*e1e2).tr()
    e2e1 = (rho*e2e1).tr()
    xx = (rho*XX).tr()
    return Qobj([[g.real, 0,0,0], [0, e1.real,e1e2.real,0],[0, e2e1.real,e2.real,0],[0, 0,0,xx.real]])#/(g+e1+e2+xx)

if __name__ == "__main__":

    OO = basis(4,0)
    XO = basis(4,1)
    OX = basis(4,2)
    XX = basis(4,3)
    sigma_m1 = OX*XX.dag() + OO*XO.dag()
    sigma_m2 = XO*XX.dag() + OO*OX.dag()
    sigma_x1 = sigma_m1+sigma_m1.dag()
    sigma_x2 = sigma_m2+sigma_m2.dag()


    w_2 = 1.0*ev_to_inv_cm
    bias = 0.*ev_to_inv_cm
    w_1 = w_2 + bias
    V = 4*92. #0.1*8065.5
    dipole_1, dipole_2 = 1., 1.
    T_EM = 6000. # Optical bath temperature
    alpha_EM = 3*inv_ps_to_inv_cm # Optical S-bath strength (from inv. ps to inv. cm)(larger than a real decay rate because dynamics are more efficient this way)
    mu = w_2*dipole_2/w_1*dipole_1

    T_1, T_2 = 300., 300. # Phonon bath temperature

    wc = 1*53. # Ind.-Boson frame phonon cutoff freq
    w0_2, w0_1 = 1000., 1000. # underdamped SD parameter omega_0
    w_xx = w_2 + w_1 + V
    alpha_1, alpha_2 = 0, 0 # Ind.-Boson frame coupling
    N_1, N_2 = 9,9 # set Hilbert space sizes
    exc = int((N_1+N_2)*1)
    num_cpus = 4
    J = J_minimal

    H_dim = w_1*XO*XO.dag() + w_2*OX*OX.dag() + w_xx*XX*XX.dag() + V*(XO*OX.dag() + OX*XO.dag())
    PARAM_names = ['w_1', 'w_2', 'V', 'bias', 'w_xx', 'T_1', 'T_2', 'wc',
                    'w0_1', 'w0_2', 'alpha_1', 'alpha_2', 'N_1', 'N_2', 'exc', 'T_EM', 'alpha_EM','mu', 'num_cpus', 'J']
    PARAMS = dict((name, eval(name)) for name in PARAM_names)

    I_dimer = qeye(4)
    I = enr_identity([N_1,N_2], exc)
    atemp = enr_destroy([N_1,N_2], exc)
    n_RC_1 = Occupation(w0_1, T_1)
    n_RC_2 = Occupation(w0_2, T_2)

    phonon_num_1 = atemp[0].dag()*atemp[0]
    phonon_num_2 = atemp[1].dag()*atemp[1]
    x_1 = (atemp[0].dag()+atemp[0])
    x_2 = (atemp[1].dag()+atemp[1])

    #initial_sys = OO*OO.dag()
    #initial_sys = 0.5*(XO+OX)*(XO+OX).dag()

    OO = tensor(OO*OO.dag(), I)
    XO = tensor(XO*XO.dag(), I)
    OX = tensor(OX*OX.dag(), I)
    XX = tensor(XX*XX.dag(), I)
    eVals, eVecs = H_dim.eigenstates()
    eVals, eVecs = zip(*sorted(zip(eVals, eVecs))) # sort them
    dark_old= eVecs[1]*eVecs[1].dag()
    bright_old= eVecs[2]*eVecs[2].dag()
    energies, states = check.exciton_states(PARAMS)
    lam_p = 0.5*(w_1+w_2)+0.5*np.sqrt((w_2-w_1)**2+4*(V**2))
    lam_m = 0.5*(w_1+w_2)-0.5*np.sqrt((w_2-w_1)**2+4*(V**2))
    bright_vec = states[0]
    dark_vec = states[1]
    dark = tensor(dark_vec*dark_vec.dag(), I)
    bright = tensor(bright_vec*bright_vec.dag(), I)
    #print  (states[1]*states[1].dag()).tr(), bright_old, states[1]*states[1].dag()
    #print (states[0]*states[0].dag()).tr(), dark_old, states[0]*states[0].dag()
    exciton_coherence = tensor(dark_vec*bright_vec.dag(), I)
    Phonon_1 = tensor(I_dimer, phonon_num_1)
    Phonon_2 = tensor(I_dimer, phonon_num_2)
    disp_1 = tensor(I_dimer, x_1)
    disp_2 = tensor(I_dimer, x_2)

    #rho_0 = tensor(initial_sys, enr_thermal_dm([N_1,N_2], exc, [n_RC_1, n_RC_2]))

    #rho_0 = rho_0/rho_0.tr()


    site_coherence = OX*XO.dag()
    # Expectation values and time increments needed to calculate the dynamics
    expects = [OO*OO.dag(), XO*XO.dag(), OX*OX.dag(), XX*XX.dag()]
    expects +=[dark, bright, exciton_coherence]
    expects +=[Phonon_1, Phonon_2, disp_1, disp_2]

    #Now we build all of the mapped operators and RC Liouvillian.

    # electromagnetic bath liouvillians

    #print sys.getsizeof(L_ns)
    opts = qt.Options(num_cpus=num_cpus)
    ncolors = len(plt.rcParams['axes.prop_cycle'])

    L_RC, H_0, A_1, A_2, A_EM, wRC_1, wRC_2, kappa_1, kappa_2 = RC.RC_mapping_UD(PARAMS)

    L_ns = EM.L_nonsecular(H_0, A_EM, PARAMS)
    ss_ns = qt.steadystate(H_0, [L_RC+L_ns], method= 'iterative-lgmres', use_precond=True)

    #print sum((ss-ss_pred).diag())
    print "Steady state is ", get_dimer_info(ss_ns)
    print "Exciton coherence is ", (ss_ns*exciton_coherence).tr()
    print "Dark population is ", (ss_ns*dark).tr()
    print "Bright population is ", (ss_ns*bright).tr()
    #ss_pred = ((-1/T_EM*0.695)*H_0).expm()
    #ss_pred = ss_pred/ss_pred.tr()

    #rho_0 = ((-1/T_1*0.695)*H_0).expm()
    rho_0 = OO*tensor(I_dimer,enr_thermal_dm([N_1,N_2], exc, [n_RC_1, n_RC_2]))
    #rho_0 = rho_0/rho_0.tr()
    """

    timelist = np.linspace(0,3,1000)*0.188
    DATA_ns = mesolve(H_0, rho_0, timelist, [L_RC+L_ns], expects, options=opts, progress_bar=True)
    fig = plt.figure(figsize=(12,6))
    ax = fig.add_subplot(111)
    vis.plot_eig_dynamics(DATA_ns, timelist, expects, ax, title='Non-secular driving\n')"""
    #print ss_pred.ptrace(0)
    check.steadystate_comparison(H_0, [L_RC+L_ns], dark)
    """
    L_p = EM.L_phenom(states, energies, I, PARAMS)
    try:
        ss_p = qt.steadystate(H_0, [L_RC+L_p], method= 'iterative-lgmres', use_precond=True)
    except:
        ss_p = qt.steadystate(H_0, [L_RC+L_p], method= 'iterative-lgmres')
    #print sum((ss-ss_pred).diag())
    print "DM is ", get_dimer_info(ss_p)

    print "Exciton coherence is ", (ss_p*exciton_coherence).tr()
    print "Dark population is ", (ss_p*dark).tr()
    print "Bright population is ", (ss_p*bright).tr()
    #print "Steady state is ", qt.steadystate(H_0)
    calculate_dynamics()
    alpha_ph = np.array([0, 10, 100, 300, 500])/pi
    biases = np.linspace(-0.25, 0.25, 81)*ev_to_inv_cm
    #try:
    #     #np.arange(60, 420, 40)/pi
    PARAMS.update({'w_1':w_2})
    #observable = exciton_coherence
    #check.get_coh_ops(PARAMS, biases, I)
    #
    """
    """
    for alpha in alpha_ph:
        PARAMS.update({'alpha_1':alpha, 'alpha_2':alpha})
        check.bias_dependence(biases, PARAMS, I)
    #
    #except Exception as err:
    #    print "data not calculated fully because", err
    #print 'now to plot things'

    vis.steadystate_coherence_plot(PARAMS, alpha_ph, biases)
    vis.steadystate_dark_plot(PARAMS, alpha_ph, biases)
    vis.steadystate_bright_plot(PARAMS, alpha_ph, biases)
    vis.steadystate_darkbright_plot(PARAMS, alpha_ph, biases)
    """
    #del L_ns
    #L_s = EM.L_secular(H_0, A_EM, eps, alpha_EM, T_EM, J, num_cpus=num_cpus)
    #L_naive = EM_lind.electronic_lindblad(w_xx, w_1, eps, V, mu, alpha_EM, T_EM, N_1, N_2, exc)
    # Set up the initial density matrix
     # you need lots of points so that coherences are well defined -> spectra
    #nonsec_check(eps, H, A_em, N) # Plots a scatter graph representation of non-secularity. Could use nrwa instead.
    #fig = plt.figure(figsize=(12, 6))
    #ax1 = fig.add_subplot(111)
    #energies = plot_manifolds(ax1, H_0)


    # Calculate dynamics

    #DATA_s = mesolve(H_0, rho_0, timelist, [L_RC+L_s], expects, progress_bar=True)
    #DATA_naive = mesolve(H_0, rho_0, timelist, [L_RC+L_naive], expects, progress_bar=True)
    #fig = plt.figure()
    #ax = fig.add_subplot(111)
    #vis.plot_RC_pop(DATA_ns, timelist, ax, title='Non-secular driving\n')

    #    fig = plt.figure(figsize=(12, 6))
    #    ax1 = fig.add_subplot(121)
    #    ax2 = fig.add_subplot(122)
    #    plot_RC_pop(DATA_ns, ax1)
    #    plot_RC_disp(DATA_ns, ax2)


    #SS, nvals = check.SS_convergence_check(eps, T_EM, T_ph, wc, w0, alpha_ph, alpha_EM, start_n=10)
    #plt.plot(nvals, SS)
    #plot_dynamics_spec(DATA_s, timelist)

    #np.savetxt('DATA/Dynamics/dimer_DATA_ns.txt', np.array([1- DATA_ns.expect[0], timelist]), delimiter = ',', newline= '\n')

    #plt.show()x
