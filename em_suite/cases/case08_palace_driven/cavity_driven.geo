// Cavidade 100 x 80 x 0.5 mm com porta lumped embutida em (a/4, b/4).
// Porta = retângulo vertical de 1 mm (x) x d (z), fixo em y = b/4,
// embutido no volume por BooleanFragments; seleção por BoundingBox.
// Gerar: gmsh -3 cavity_driven.geo -o cavity_driven.msh -format msh2

SetFactory("OpenCASCADE");

a = 0.100; b = 0.080; d = 0.0005;
pw = 0.001;                       // largura da porta
px0 = a/4 - pw/2;

Box(1) = {0, 0, 0, a, b, d};

// retângulo da porta no plano XY, depois rodado para XZ em y = b/4
Rectangle(100) = {px0, b/4, 0, pw, d};
Rotate {{1, 0, 0}, {px0, b/4, 0}, Pi/2} { Surface{100}; }

f() = BooleanFragments{ Volume{1}; Delete; }{ Surface{100}; Delete; };

eps = 1e-5;
port() = Surface In BoundingBox{px0-eps, b/4-eps, -eps,
                                px0+pw+eps, b/4+eps, d+eps};
top()  = Surface In BoundingBox{-eps, -eps, d-eps, a+eps, b+eps, d+eps};
bot()  = Surface In BoundingBox{-eps, -eps, -eps, a+eps, b+eps, eps};
sx0()  = Surface In BoundingBox{-eps, -eps, -eps, eps, b+eps, d+eps};
sxa()  = Surface In BoundingBox{a-eps, -eps, -eps, a+eps, b+eps, d+eps};
sy0()  = Surface In BoundingBox{-eps, -eps, -eps, a+eps, eps, d+eps};
syb()  = Surface In BoundingBox{-eps, b-eps, -eps, a+eps, b+eps, d+eps};
vols() = Volume{:};

Physical Volume("fr4", 1) = {vols()};
Physical Surface("pec_planos", 2) = {top(), bot()};
Physical Surface("pmc_laterais", 3) = {sx0(), sxa(), sy0(), syb()};
Physical Surface("porta", 10) = {port()};

MeshSize{ PointsOf{ Volume{vols()}; } } = 0.004;
MeshSize{ PointsOf{ Surface{port()}; } } = 0.0005;
