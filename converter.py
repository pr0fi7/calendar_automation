from csv_ical import Convert

convert = Convert()
convert.CSV_FILE_LOCATION = 'test2.csv'
convert.SAVE_LOCATION = "mark2004kyki@gmail.com.ical/mark2004kyki@gmail.com.ics"
convert.read_ical(convert.SAVE_LOCATION)
convert.make_csv()
convert.save_csv(convert.CSV_FILE_LOCATION)