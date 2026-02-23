clients = [
    { "m_name": "LF Markey", "m_id": 11, "tb_name": "LF Markey", "tb_rma_prov": "Loop", "warehouse_id": 3 },
    { "m_name": "Lou Swim", "m_id": 25, "tb_name": "Lou Swim", "tb_rma_prov": "Work Capture", "warehouse_id": 3 },
    { "m_name": None, "m_id": None, "tb_name": "Mister Zimi", "tb_rma_prov": "Loop", "warehouse_id": 3 },
    { "m_name": "Nude Lucy", "m_id": 16, "tb_name": "Nude Lucy", "tb_rma_prov": "Work Capture", "warehouse_id": 3 },
    { "m_name": None, "m_id": None, "tb_name": "One Teaspoon", "tb_rma_prov": "Work Capture", "warehouse_id": 3 },
    { "m_name": None, "m_id": None, "tb_name": "OW Intimates", "tb_rma_prov": "Work Capture", 	"warehouse_id": 3 },
    { "m_name": "Pink City Prints", "m_id": 15, "tb_name": "Pink City Prints", "tb_rma_prov": "Work Capture", 	"warehouse_id": 3 },
    { "m_name": None, "m_id": None, "tb_name": "Posse", "tb_rma_prov": "Webhooks", "warehouse_id": 3 },
    { "m_name": "Sancia", "m_id": 23, "tb_name": "Sancia", "tb_rma_prov": "Loop", "warehouse_id": 3 },
    { "m_name": None, "m_id": None, "tb_name": "Sau Lee", "tb_rma_prov": "AfterShip", "warehouse_id": 3 },
    { "m_name": None, "m_id": None, "tb_name": "seventy + mochi", "tb_rma_prov": "Work Capture", "warehouse_id": 3 },
    { "m_name": None, "m_id": None, "tb_name": "SNDYS", "tb_rma_prov": "Webhooks",	"warehouse_id": 3 },
    { "m_name": "Third Form", "m_id": 22, "tb_name": "Third Form", "tb_rma_prov": "Loop",	"warehouse_id": 3 },
    { "m_name": "TT Studios",	"m_id": 7,	"tb_name":"TT Studios",	"tb_rma_prov":"Loop",	"warehouse_id": 3 },
    { "m_name": None,	"m_id":"None",	"tb_name":"Zeynep Arcay","tb_rma_prov":"Work Capture","warehouse_id":"3"},
    { "m_name": None,	"m_id":"None",	"tb_name":"Dala","tb_rma_prov":"AfterShip, Work Capture","warehouse_id":"3"},
    { "m_name":"Deiji Studios","m_id":"10","tb_name":"Deiji Studios","tb_rma_prov":"Swap, Swap V2","warehouse_id":"3"},
    { "m_name":"Emilia Wickstead", 	"m_id":"20", 	"tb_name":"Emilia Wickstead", 	"tb_rma_prov":"AfterShip, Loop", "warehouse_id": 3},
    { "m_name":"Bronze Snake", 	"m_id":"None", 	"tb_name":"Bronze Snake", 	"tb_rma_prov":"Webhooks", "warehouse_id": 3},
    { "m_name":"Cin Cin", 	"m_id":"None", 	"tb_name":"Cin Cin", 	"tb_rma_prov":"Loop", "warehouse_id": 3},
    { "m_name":"Clea", 	"m_id":"None", 	"tb_name":"Clea", 	"tb_rma_prov":"Work Capture", "warehouse_id": 3},
    { "m_name":"TEST CLIENT", 	"m_id":3, 	"tb_name":"test client", 	"tb_rma_prov":"Work Capture", "warehouse_id": 3}
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