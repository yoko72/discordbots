from pandas import Series

tokens_dict = {
    "Hurry":
        "ODYxNjI1OTgxMTQ3MDIxMzEy.YOMhug.HMywwtH1Vez1DQl9zsMY4GwYFnk",
    "Mary":
        "ODYwNTg3MTQwNDI0NjYzMDYw.YN9aOw.OUvoAWrQDcGzS4Ao8Z6W9BQqKz0",
    "tempo":
        "NTE3Njc2NTAwNzcwNjE5NDEy.DuFt1g.Pu5aTOE8BTsZ3Aakahlix-3Z8lI",
    "tempo_canary":
        "NTIwMDczNzQ3NjQ2OTA2MzY4.DvVLCQ.b-TUGxY0NqtPhkLcQthtY0eW3m4",
    "tempo_debugging":
        "NTg4NTk2OTc2NjY1MjMxMzgw.XQHdgg.weVZjGBCYm-4IaS98KOe_G35Mjg",
    "tempo_helper":
        "NzE3OTI2NzU0MDY4NDYzNzA2.XthcBA.xukSnywiq43K_3B4JF_4kXkWR0A",
    "saba":
        "NTEyNjA0NTgxNDE5ODEwODMx.Ds8B7w.C2SomjcI8wYT-_YCeMN3faZ3LT4"
}

tokens = Series(tokens_dict)
# tokens["saba"] == tokens.saba

server_dict = {
    "実験場":853249947952087050,
    "作業鯖":860542726189875250,
    "Merihari":860542726189875250,
    "ローマ":860542726189875250,
    "MERIHARI":860542726189875250,
    "メリハリ":860542726189875250
}
servers_id = Series(server_dict)

channel_dict = {
    "ボット":860569494258974761
}

channels = Series(channel_dict)

member_dict = {
    "とんかつ":381618666266951690,
    "やるぞう":747313058199896074
}

members = Series(member_dict)

def SQL_tempo_host():
    return "127.0.0.1"#"tempo-1.cftbfkcpxx8c.ap-northeast-1.rds.amazonaws.com"

def SQL_tempo_pass():
    return "9yokoyto"#'CmUtYISWKT9fvgx2h13k'

def SQL_tempo_port():
    return 3306#22663

def SQL_tempo_user():
    return "admin"

def karaoke_tempo():
    return "NzI5NTE2NzcyNzc1OTUyNDI0.XwKIyg.Tx7YJj5CU4HuiFJeqi065sFBw6E"