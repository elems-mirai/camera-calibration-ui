import numpy as np

camera_data = './labeled_c1_camera_test2/front/camera_data'

new_cameraMatrix = np.load(camera_data + "/new_camera_matrix.npy")
tvec = np.load(camera_data + "/tvec.npy")
R_matrix = np.load(camera_data + "/rotation_matrix.npy")

inv_new_cameraMatrix = np.linalg.inv(new_cameraMatrix)
inv_R_matrix = np.linalg.inv(R_matrix)

def def_cord(u, v, scalingfactor):
    uv_1 = np.array([[u, v, 1]], dtype=np.float32)
    uv_1 = uv_1.T
    suv_1 = scalingfactor * uv_1
    xyz_c = inv_new_cameraMatrix.dot(suv_1)
    xyz_c = xyz_c - tvec
    XYZ = inv_R_matrix.dot(xyz_c)
    return XYZ

def img2world(u, v):
    A_point = def_cord(u, v, scalingfactor=0)
    B_point = def_cord(u, v, scalingfactor=1)
    Zc = 0

    eq = (Zc - A_point[2]) / (B_point[2] - A_point[2])
    Xc = eq * (B_point[0] - A_point[0]) + A_point[0]
    Yc = eq * (B_point[1] - A_point[1]) + A_point[1]
    return [Xc[0], Yc[0], Zc]

# TEST 1 
# FRONT CAMERA
# img_pts = [[990,1242],[1182,693],[1309,357],[1482,346],[1368,83],[946,110]]
# wrld_pts = [[50,50,0],[100,160,0],[150,270,0],[200,270,0],[200,410,0],[50,410,0]]
# BACK CAMERA
# img_pts = [[942, 890], [930,614],[665,370], [1219,347], [662,136], [1197,115] , [1270,873],   [1244,598],    [917,360],   [664,905],   [664,628],    [39,935],     [67, 655],     [93, 390],     [114, 157],   [906,126]]
# wrld_pts = [[50, 0, 0],[100,0,0],[150,50,0],[150,-60,0],[200,50,0],[200,-60,0], [50, -60, 0], [100, -60, 0], [150, 0, 0], [50, 50, 0], [100, 50, 0], [50, 160, 0], [100, 160, 0], [150, 160, 0], [200, 160, 0], [200, 0, 0]]
# # TEST 2
# FRONT CAMERA
img_pts = [[990,1243],[1186,693], [1308,356], [1481,346], [1367,84],  [946,109], [958,377],  [1129,366] , [1857,1199], [1274,1228],  [1569,1215],  [970,702],    [1409,681],    [1625,668],    [1086,100],    [1227,93]]
wrld_pts = [[50,50,0],[100,160,0],[150,270,0],[200,270,0],[200,410,0],[50,410,0],[50,270,0], [100,270,0], [200,50,0] , [100, 50, 0], [150, 50, 0], [50, 160, 0], [150, 160, 0], [200, 160, 0], [100, 410, 0], [150, 410, 0]]
# BACK CAMERA
# img_pts = [[942.0, 889.0],   
#            [929.0,613.0],  
#            [661.0,137.0],   
#            [1195.0,116.0],   
#            [907.0,127.0],   
#            [39.0,936.0],
#            [918,361]
#            ]
# wrld_pts = [[50.0, 0.0, 0.0],
#             [100.0,0.0,0.0],
#             [200.0,50.0,0.0],
#             [200.0,-60.0,0.0],
#             [200.0,0.0,0.0], 
#             [50.0, 160.0, 0.0],
#             [150,0,0],   
#             ]
for i in range(len(img_pts)):
    u, v = img_pts[i]
    XYZ = img2world(u, v)
    # print("XYZ:", XYZ)
    XYZ = np.array(XYZ, dtype=np.float32)

    correct = np.array(wrld_pts[i], dtype=np.float32)
    error = correct - XYZ
    # ---- keep original printing ----
    print(
        "--------------------------------------------------------------------------------------------------------------------------------------------"
    )
    print(
        "u=",
        u,
        "v=",
        v,
        " || ",
        "correct:",
        wrld_pts[i],
        " || ",
        "Predicted:",
        np.around(XYZ[0], 2),
        " ",
        np.around(XYZ[1], 2),
        " ",
        XYZ[2],
        " || ",
        "error:",
        error,
    )
