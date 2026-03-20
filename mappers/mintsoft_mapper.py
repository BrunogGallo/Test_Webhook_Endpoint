clients = [
  # { "m_name": "Acler", "m_id": 19, "tb_name": "acler", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  { "m_name": "Brodie", "m_id": 5, "tb_name": "brodie", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Deiji Studios", "m_id": 10, "tb_name": "deiji studios", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  { "m_name": "Emilia Wickstead", "m_id": 20, "tb_name": "emilia wickstead", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Emily Lovelock", "m_id": 18, "tb_name": "emily lovelock", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Holiday Company", "m_id": 4, "tb_name": "holiday company", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "House of Sunny", "m_id": 12, "tb_name": "house of sunny", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Huishan Zhang", "m_id": 17, "tb_name": "huishan zhang", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Kivari", "m_id": 13, "tb_name": "kivari", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  { "m_name": "LF Markey", "m_id": 11, "tb_name": "lf markey", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Lorna Murray", "m_id": 24, "tb_name": "lorna murray", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Lou Swim", "m_id": 25, "tb_name": "lou swim", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Maggie The Label", "m_id": 27, "tb_name": "maggie the label", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  { "m_name": "Nude Lucy", "m_id": 16, "tb_name": "nude lucy", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Pink City Prints", "m_id": 15, "tb_name": "pink city prints", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Rove", "m_id": 8, "tb_name": "rove", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Sancia", "m_id": 23, "tb_name": "sancia", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Shirty Group", "m_id": 9, "tb_name": "shirty group", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Staple & Hue", "m_id": 21, "tb_name": "staple & hue", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Theo", "m_id": 14, "tb_name": "theo", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Third Form", "m_id": 22, "tb_name": "third form", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "TT Studios", "m_id": 7, "tb_name": "tt studios", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  # { "m_name": "Ziah", "m_id": 26, "tb_name": "ziah", "tb_rma_prov": "Work Capture", "warehouse_id": 3}
  { "m_name": "TEST CLIENT", "m_id": 3, "tb_name": "test client wholesale", "tb_rma_prov": "Work Capture", "warehouse_id": 3},
  { "m_name": "TEST CLIENT", "m_id": 3, "tb_name": "test client ecommerce", "tb_rma_prov": "Work Capture", "warehouse_id": 5}
]

def map_client(tb_name:str):
    for client in clients:
        if client["tb_name"].lower() == tb_name.lower():
            return client["m_id"]
    return None

def map_warehouse(tb_name:str):
    for client in clients:
        if client["tb_name"].lower() == tb_name.lower():
            return client["warehouse_id"]
    return None