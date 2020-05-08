/*
A KBase module: bogus
*/

module special {

    typedef structure {
        string report_name;
    } SlurmOutput;


   funcdef slurm(UnspecifiedObject params) returns (SlurmOutput output);

};
