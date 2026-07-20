// Cavidade plano-a-plano 100 x 80 x 0.5 mm para eigenmode no Palace.
// Condições: PEC em z = 0 e z = d (planos), PMC nas 4 laterais
// (parede magnética = modelo de cavidade ideal) -> f_mn analítico
// exato como referência.
// Gerar malha:  gmsh -3 cavity.geo -o cavity.msh -format msh2

SetFactory("OpenCASCADE");

a = 0.100;   // m
b = 0.080;
d = 0.0005;

Box(1) = {0, 0, 0, a, b, d};

// tamanho de elemento: ~lambda/25 a 1.8 GHz em eps_r 4.4 (~3 mm)
MeshSize{ PointsOf{ Volume{1}; } } = 0.004;

// superfícies do box OpenCASCADE: 1=x0, 2=xa, 3=y0, 4=yb, 5=z0, 6=zd
Physical Volume("fr4", 1) = {1};
Physical Surface("pec_planos", 2) = {5, 6};
Physical Surface("pmc_laterais", 3) = {1, 2, 3, 4};
