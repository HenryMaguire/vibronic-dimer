##### a function to construct and solve the RC master equation ####

# make qutip available in the rest of the notebook
from qutip import *

#import the functions from numpy, a numerical array handler
from numpy import matrix
from numpy import linalg

from scipy import *


#import enr_functions as excres


def lin_construct(O):
	Od = O.dag()
	L = 2. * spre(O) * spost(Od) - spre(Od * O) - spost(Od * O)
	return L

def rate_up(w, beta, gamma):
	n = 1 / (exp(beta * w) - 1.)
	rate = 0.5 * pi * gamma * n
	return rate

def rate_down(w, beta, gamma):
	n = 1 / (exp(beta * w) - 1.)
	rate = 0.5 * pi * gamma * (n + 1. )
	return rate


def	EM_dissipator(wXX, w2, eps, V, mu, gamma, EM_temp, N, exc):
#
# A function  to build the Liouvillian describing the processes due to the
# electromagnetic field (without Lamb shift contributions). The important
# parameters to consider here are:
#
#	wXX = biexciton splitting
#	w1 = splitting of site 1
#	eps = bias between site 1 and 2
#	V = tunnelling rate between dimer
#	mu = scale factor for dipole moment of site 2
# 	gamma = bare coupling to the environment.
#	EM_temp =  temperature of the electromagnetic environment
# 	N = the number of states in the RC
#	exc = number of excitations kept in the ENR basis
########################################################

	#important definitions for the the ENR functions:
	# the dimension list for the RCs is:
	dims = [N] * 2
	#2 is the number of modes taken

	#and dimension of the sysetm:
	Nsys = 4

	#Load the ENR dictionaries
	nstates, state2idx, idx2state = enr_state_dictionaries(dims, exc)


	#boltzmann constant in eV
	k_b = 0.695
	thermal_energy = k_b * EM_temp
	beta = 1 / thermal_energy

	# the site basis is:
	bi = Qobj(array([1, 0., 0., 0]))
	b2 = Qobj(array([0., 0., 1., 0.]))
	b1 = Qobj(array([0., 1., 0., 0.]))
	gr = Qobj(array([0., 0., 0., 1.]))
	#H = gr*gr.dag()
	# the eigenstate splitting is given by:
	eta = sqrt(eps ** 2. + 4. * V ** 2.)

	# and the eigenvalues are:
	lam_p = 0.5 * (2 * w2 + eps + eta)
	lam_m = 0.5 * (2 * w2 + eps - eta)
	# first we define the eigenstates:
	psi_p = (sqrt( eta - eps) * b1 + sqrt( eta + eps) * b2) / sqrt(2 * eta)
	psi_m = (- sqrt(eta + eps) * b1 + sqrt(eta - eps) * b2) / sqrt(2 * eta)
	HDim = (w2 + eps) * b1 * b1.dag() + w2 * b2 * b2.dag() + wXX * bi * bi.dag()
	HDim = HDim + V * (b1 * b2.dag() + b2 * b1.dag())
	energies, states = HDim.eigenstates()
	#print psi_p.dag()*states[1], psi_p.dag()*states[2], psi_m.dag()*states[1], psi_m.dag()*states[2]
	psi_m = states[1]
	psi_p = states[2]
	# Now the system eigenoperators
	#ground -> dressed state transitions
	Alam_p = (sqrt( eta - eps) + (1 - mu) * sqrt(eta + eps)) / sqrt(2 * eta)
	Alam_p *= gr * (psi_p.dag())
	Alam_p = tensor(enr_identity(dims, exc), Alam_p)

	Alam_m = - (sqrt( eta + eps) - (1 - mu) * sqrt(eta - eps)) / sqrt(2 * eta)
	Alam_m *= gr * (psi_m.dag())
	Alam_m = tensor(enr_identity(dims, exc), Alam_m)

	#print(Alam_m)
	#dressed state -> biexciton transitions
	Alam_p_bi = (sqrt( eta - eps) + (1 - mu) * sqrt(eta + eps)) / sqrt(2 * eta)
	print Alam_p_bi
	Alam_p_bi *= (psi_p) * (bi.dag())
	Alam_p_bi = tensor(enr_identity(dims, exc), Alam_p_bi)


	Alam_m_bi = - (sqrt( eta + eps) - (1 - mu) * sqrt(eta - eps)) / sqrt(2 * eta)
	Alam_m_bi = - (sqrt( eta + eps) - (1 - mu) * sqrt(eta - eps)) / sqrt(2 * eta)
	print Alam_m_bi
	Alam_m_bi *= (psi_m) * (bi.dag())
	Alam_m_bi = tensor(enr_identity(dims, exc), Alam_m_bi)



	# Now the dissipators and there associated rates are are given by:
	gam_p_emm = rate_down(lam_p, beta, gamma)

	L1_emission = lin_construct(Alam_p)

	gam_p_abs = rate_up(lam_p, beta, gamma)
	L1_absorption = lin_construct(Alam_p.dag())

	gam_m_emm = rate_down(lam_m, beta, gamma)
	L2_emission = lin_construct(Alam_m)

	gam_m_abs = rate_up(lam_m, beta, gamma)
	L2_absorption = lin_construct(Alam_m.dag())

	gam_bi_p_emm = rate_down(wXX-lam_p, beta, gamma)
	L3_emission = lin_construct(Alam_p_bi)

	gam_bi_p_abs = rate_up(wXX-lam_p, beta, gamma)
	L3_absorption = lin_construct(Alam_p_bi.dag())

	gam_bi_m_emm = rate_down(wXX-lam_m, beta, gamma)
	L4_emission = lin_construct(Alam_m_bi)

	gam_bi_m_abs = rate_up(wXX-lam_m, beta, gamma)
	L4_absorption = lin_construct(Alam_m_bi.dag())


	#So the Liouvillian
	Li = gam_p_emm * L1_emission + gam_p_abs * L1_absorption
	Li = Li + gam_m_emm * L2_emission + gam_m_abs * L2_absorption
	Li = Li + gam_bi_p_emm * L3_emission + gam_bi_p_abs * L3_absorption
	Li = Li + gam_bi_m_emm * L4_emission + gam_bi_m_abs * L4_absorption

	return Li